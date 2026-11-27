"""Account access coordination. Host tools execute browser/Gmail actions; no secrets input."""
import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from private_settings import Settings, site_origin


def need(value, message):
    if not value:
        raise ValueError(message)


def address(value):
    need(isinstance(value, str) and re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", value),
         'Use an exact email address, not a display name.')
    return value.casefold()


def origin(value):
    result = site_origin(value)
    need(value == result, 'Supply only the exact HTTPS origin; never a token or verification URL.')
    return result


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        need(result.tzinfo is not None, 'Timestamp needs a timezone.')
        return result
    except (AttributeError, TypeError, ValueError):
        raise ValueError('Supply a valid timezone-aware timestamp.') from None


def verification_policy(request, site):
    enabled = request.get('enabled')
    need(type(enabled) is bool, 'Choose whether account verification is allowed.')
    if not enabled:
        return {'enabled': False}
    senders = request.get('senders', '')
    origins = request.get('origins', '')
    need(isinstance(senders, str) and isinstance(origins, str), 'Use comma-separated senders and origins.')
    senders = sorted(set(address(x.strip()) for x in senders.split(',') if x.strip()))
    destinations = sorted(set([site] + [origin(x.strip()) for x in origins.split(',') if x.strip()]))
    need(0 < len(senders) <= 10 and len(destinations) <= 10, 'Approve one to ten exact senders and destinations.')
    return dict(enabled=True, mailbox=address(request.get('mailbox')), senders=senders,
                origins=destinations, revision=uuid.uuid4().hex)


def permission_token(site, defaults):
    # Any permission/identity change invalidates the outstanding attempt, including
    # disable/re-enable verification. Never include a password in returned evidence.
    policy = {k: v for k, v in site.items() if k != 'password'}
    policy['default_email'] = defaults.get('email')
    return hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()


class AccountFlow:
    def __init__(self, workspace):
        self.workspace = workspace
        self.settings = Settings(workspace.root)

    def run(self, request):
        need(isinstance(request, dict), 'Supply an account-flow request.')
        op = request.get('op')
        fields = {
            'start': {'job_id', 'origin', 'page_confirmed'},
            'inspect': {'flow_id'},
            'begin': {'flow_id', 'page_origin', 'page_confirmed'},
            'observe': {'flow_id', 'page_origin', 'page_confirmed', 'result'},
            'verify-begin': {'flow_id', 'page_origin', 'page_confirmed', 'connected_account',
                'recipient', 'sender', 'message_id', 'received_at', 'link_origin', 'mode', 'matches_attempt'},
        }
        need(op in fields and set(request) <= fields[op] | {'op'},
             'Unsupported fields: never supply passwords, codes, email bodies or activation URLs.')
        state = self.workspace.read()
        result = {}
        now = datetime.now(timezone.utc)

        def update(data):
            flows = data['account_flows']
            if op == 'start':
                site_url = origin(request.get('origin'))
                jid = request.get('job_id')
                need(request.get('page_confirmed') is True, 'Inspect the live employer, role and account page first.')
                site = data['sites'].get(site_url, {})
                need(site.get('allow_login') or site.get('allow_signup'), 'Approve this exact site first.')
                job = state['jobs'].get(jid)
                need(job and job['status'] in {'Selected', 'Preparing', 'Filling', 'Needs attention'},
                     'Choose a selected unfinished application; never resume an uncertain submission.')
                from backlog import freshness_ok
                need(freshness_ok(job), 'Recheck the live posting and application route first.')
                # Resume an existing attempt instead of resetting its retry budget.
                existing = next((f for f in flows.values() if f['job_id'] == jid and f['origin'] == site_url
                                 and f['state'] != 'active'), None)
                if existing:
                    result.update(existing)
                    return
                username = site.get('username') or data['signup'].get('email')
                need(username, 'Save the site username or default email first.')
                action = 'login_ready' if site.get('password') and site.get('allow_login') else 'inspect_signup'
                ident = uuid.uuid4().hex
                flow = dict(id=ident, job_id=jid, origin=site_url, username=username, state=action,
                            created_at=now.isoformat(), expires_at=(now + timedelta(minutes=30)).isoformat(),
                            permission_token=permission_token(site, data['signup']))
                flows[ident] = flow
            else:
                flow = flows.get(request.get('flow_id'))
                need(flow is not None, 'Unknown account attempt.')
                if op == 'inspect':
                    result.update(flow)
                    return
                site = data['sites'].get(flow['origin'], {})
                need(flow['permission_token'] == permission_token(site, data['signup']),
                     'Site permissions or identity changed; request candidate assistance.')
                need(instant(flow['expires_at']) > now, 'Account attempt expired; request candidate assistance.')
                job = state['jobs'].get(flow['job_id'])
                need(job and job['status'] in {'Selected', 'Preparing', 'Filling', 'Needs attention'},
                     'Application is no longer eligible for account work.')
                need(request.get('page_confirmed') is True, 'Inspect the current live page first.')
                page_origin = origin(request.get('page_origin'))
                need(page_origin == flow['origin'], 'Return to the approved career-site page first.')
                status = flow['state']
                if op == 'begin':
                    need(status in {'login_ready', 'signup_ready'}, 'Action already started or blocked; inspect, never replay.')
                    purpose = status.split('_')[0]
                    need(site.get('allow_' + purpose), 'This account action is not approved.')
                    need(purpose != 'signup' or not flow.get('signup_attempted'),
                         'Signup already attempted; request candidate assistance instead of creating another account.')
                    if purpose == 'signup':
                        flow['signup_attempted'] = True
                    flow['state'] = purpose + '_started'
                    flow['action_at'] = now.isoformat()
                elif op == 'observe':
                    observed = request.get('result')
                    transitions = {
                        'login_started': {'authenticated': 'active', 'account_not_found': 'signup_ready',
                                          'verification_required': 'blocked'},
                        'inspect_signup': {'signup_form': 'signup_ready', 'authenticated': 'active'},
                        'signup_started': {'verification_required': 'verification_wait', 'authenticated': 'active'},
                        'verification_started': {'authenticated': 'active', 'account_verified': 'verified'},
                        'verified': {'login_form': 'login_ready', 'authenticated': 'active'},
                    }
                    if observed in {'captcha', 'mfa', 'invalid_credentials', 'unknown', 'account_exists', 'rejected'}:
                        flow['state'] = 'blocked'
                    else:
                        need(observed in transitions.get(status, {}), 'Observation is not valid for this step.')
                        next_state = transitions[status][observed]
                        if next_state == 'signup_ready':
                            need(site.get('allow_signup'), 'Signup requires its own site permission.')
                        flow['state'] = next_state
                    flow['last_observation'] = observed
                    flow['observed_at'] = now.isoformat()
                elif op == 'verify-begin':
                    need(status == 'verification_wait', 'Only verify the current pending signup; never replay activation.')
                    policy = site.get('verification', {})
                    need(policy.get('enabled') is True, 'Enable separate account-verification permission first.')
                    mailbox = policy['mailbox']
                    need(address(request.get('connected_account')) == mailbox == address(request.get('recipient'))
                         == address(flow['username']), 'Connected mailbox, recipient and signup email must match.')
                    need(address(request.get('sender')) in policy['senders'], 'Sender is not approved for verification.')
                    need(request.get('matches_attempt') is True, 'Verify the site, account and current signup context in the email.')
                    received = instant(request.get('received_at'))
                    need(instant(flow['action_at']) <= received <= now, 'Email predates this signup or has a future date.')
                    message_id = request.get('message_id')
                    need(isinstance(message_id, str) and re.fullmatch(r'[a-fA-F0-9]{1,64}', message_id), 'Use the actual Gmail message ID.')
                    need(not any(f.get('message_id') == message_id and f.get('mailbox') == mailbox for f in flows.values()),
                         'This verification message was already used; inspect the page instead.')
                    mode = request.get('mode')
                    need(mode in {'link', 'code'}, 'Choose link or code verification.')
                    destination = origin(request.get('link_origin'))
                    need(destination in policy['origins'], 'Verification destination is not approved.')
                    if mode == 'code':
                        need(destination == flow['origin'], 'Enter a code only on the approved signup page.')
                    flow.update(state='verification_started', message_id=message_id, mailbox=mailbox,
                                verification_origin=destination, verification_mode=mode)
            result.update(flow)
        self.settings.change(update)
        # Return only fixed workflow metadata. Tokens/codes are never inputs or stored.
        result.pop('permission_token', None)
        result['next_action'] = {
            'login_ready': 'Inspect the login form, then begin before filling and clicking Login.',
            'inspect_signup': 'Inspect the signup option; do not guess that a failed login means no account exists.',
            'signup_ready': 'Inspect the signup form and required terms, then begin before creating the account.',
            'login_started': 'Inspect the live result; do not retry the login automatically.',
            'signup_started': 'Inspect the live result; do not create another account.',
            'verification_wait': 'Check the exact approved Gmail account for this signup, then verify-begin.',
            'verification_started': 'Inspect live activation state; never replay the link or code after ambiguity.',
            'verified': 'Return to the career site and inspect whether login is required.',
            'active': 'Inspect the original job form and resume under existing application permissions.',
            'blocked': 'Pause this job with a safe assistance request and continue another eligible job.',
        }[result['state']]
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--expect-workspace', type=Path, required=True)
    parser.add_argument('--input', type=Path, help='Non-secret JSON request; omit to read stdin')
    args = parser.parse_args()
    try:
        from toolkit import Workspace
        need(args.workspace.resolve() == args.expect_workspace.resolve(), 'Wrong workspace; confirm candidate first.')
        request = json.loads(args.input.read_text(encoding='utf-8-sig') if args.input else sys.stdin.read())
        print(json.dumps(AccountFlow(Workspace(args.workspace)).run(request)))
        return 0
    except (ValueError, OSError):
        # Inputs may accidentally contain secrets. Never echo them or a traceback.
        print(json.dumps({'error': 'Account step stopped. Check the request, exact-site permission, mailbox, live page and attempt state. Do not retry an ambiguous action.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
