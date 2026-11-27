import base64
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from test_skill import toolkit
from private_settings import Settings
from account_flow import AccountFlow


SITE = 'https://careers.example.invalid'
MAIL = 'candidate@example.invalid'
SENDER = 'accounts@example.invalid'


def stamp(minutes=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


class AccountFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ws = toolkit.Workspace(self.root)
        self.ws.initialize()
        # Portable synthetic storage fixture only. Real encryption is covered by AccountTests.
        self.crypt = patch.object(Settings, 'crypt', lambda self, data, decrypt=False:
                                  base64.b64decode(data) if decrypt else base64.b64encode(data))
        self.crypt.start()
        self.addCleanup(self.crypt.stop)
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(self.root)
        self.settings.save(dict(kind='signup', email=MAIL))
        self.settings.save(dict(kind='site', url=SITE, allow_login=True, allow_signup=True))
        self.policy()
        self.jid = self.ws.mutate(dict(op='job-add', title='Fixture', company='Synthetic',
            description='Synthetic posting', source='Fixture', url=SITE+'/job'))['job_id']
        self.ws.mutate(dict(op='freshness-record', job_id=self.jid, route_url=SITE+'/apply',
            checked_at=stamp(), open=True, route_valid=True, evidence='Synthetic route'))
        self.ws.mutate(dict(op='select', job_id=self.jid))
        self.flow = AccountFlow(self.ws)

    def policy(self, **changes):
        return self.settings.save(dict(dict(kind='verification', url=SITE, enabled=True,
            mailbox=MAIL, senders=SENDER, origins=''), **changes))

    def start(self):
        return self.flow.run(dict(op='start', job_id=self.jid, origin=SITE, page_confirmed=True))

    def step(self, ident, op, **changes):
        return self.flow.run(dict(op=op, flow_id=ident, page_origin=SITE, page_confirmed=True, **changes))

    def pending(self):
        f = self.start()
        self.step(f['id'], 'observe', result='signup_form')
        self.step(f['id'], 'begin')
        self.step(f['id'], 'observe', result='verification_required')
        return f['id']

    def mail(self, **changes):
        return dict(dict(connected_account=MAIL, recipient=MAIL, sender=SENDER,
            message_id='abcdef123', received_at=stamp(), mode='link', link_origin=SITE,
            matches_attempt=True), **changes)

    def test_signup_activation_then_login_preserves_application_permissions(self):
        before = self.ws.read()
        ident = self.pending()
        verified = self.step(ident, 'verify-begin', **self.mail())
        self.assertEqual(verified['state'], 'verification_started')
        self.step(ident, 'observe', result='account_verified')
        self.step(ident, 'observe', result='login_form')
        self.step(ident, 'begin')
        self.assertEqual(self.step(ident, 'observe', result='authenticated')['state'], 'active')
        self.assertEqual(before, self.ws.read())
        self.assertNotIn('account_flows', json.dumps(self.ws.read()))
        self.assertNotIn('permission_token', verified)

    def test_login_missing_account_vs_ambiguous_error(self):
        self.settings.save(dict(kind='site', url=SITE, password='Synthetic-only!', allow_login=True, allow_signup=True))
        ident = self.start()['id']
        self.step(ident, 'begin')
        self.assertEqual(self.step(ident, 'observe', result='account_not_found')['state'], 'signup_ready')
        self.step(ident, 'begin')
        self.assertEqual(self.step(ident, 'observe', result='account_exists')['state'], 'blocked')
        self.assertEqual(self.start()['id'], ident)
        with self.assertRaises(ValueError):
            self.step(ident, 'begin')

    def test_invalid_credentials_never_trigger_signup(self):
        self.settings.save(dict(kind='site', url=SITE, password='Synthetic-only!', allow_login=True, allow_signup=True))
        ident = self.start()['id']
        self.step(ident, 'begin')
        self.assertEqual(self.step(ident, 'observe', result='invalid_credentials')['state'], 'blocked')
        with self.assertRaises(ValueError):
            self.step(ident, 'observe', result='signup_form')

    def test_wrong_mail_scope_and_secret_fields_rollback(self):
        ident = self.pending()
        before = self.settings.read()
        for change in [dict(connected_account='other@example.invalid'), dict(recipient='other@example.invalid'),
                       dict(sender='attacker@example.invalid'), dict(received_at=stamp(-60)),
                       dict(received_at=stamp(5)), dict(link_origin='https://evil.invalid'),
                       dict(link_origin=SITE+'/verify?token=synthetic'), dict(matches_attempt=False),
                       dict(mode='password_reset'), dict(message_id='not-a-gmail-id'), dict(code='synthetic')]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.step(ident, 'verify-begin', **self.mail(**change))
                self.assertEqual(before, self.settings.read())

    def test_code_replay_and_interrupted_action(self):
        ident = self.pending()
        self.step(ident, 'verify-begin', **self.mail(mode='code'))
        with self.assertRaises(ValueError):
            self.step(ident, 'verify-begin', **self.mail(mode='code'))
        resumed = self.start()
        self.assertEqual(resumed['id'], ident)
        self.assertEqual(resumed['state'], 'verification_started')
        self.assertEqual(self.step(ident, 'observe', result='unknown')['state'], 'blocked')

    def test_revocation_expiry_and_wrong_page(self):
        ident = self.pending()
        with self.assertRaises(ValueError):
            self.flow.run(dict(op='observe', flow_id=ident, page_origin='https://evil.invalid',
                               page_confirmed=True, result='authenticated'))
        self.policy(enabled=False)
        with self.assertRaises(ValueError):
            self.step(ident, 'verify-begin', **self.mail())
        self.policy()
        with self.assertRaises(ValueError):
            self.step(ident, 'verify-begin', **self.mail())
        # Restore the original policy token for the expiry-specific synthetic check.
        from account_flow import permission_token
        def expire(data):
            data['account_flows'][ident]['permission_token'] = permission_token(data['sites'][SITE], data['signup'])
            data['account_flows'][ident]['expires_at'] = stamp(-1)
        self.settings.change(expire)
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.step(ident, 'verify-begin', **self.mail())

    def test_external_activation_origin_requires_permission_and_no_second_signup(self):
        external = 'https://verify.example.invalid'
        self.policy(origins=external)
        ident = self.pending()
        with self.assertRaises(ValueError):
            self.step(ident, 'verify-begin', **self.mail(mode='code', link_origin=external))
        self.step(ident, 'verify-begin', **self.mail(link_origin=external))
        self.step(ident, 'observe', result='account_verified')
        self.step(ident, 'observe', result='login_form')
        self.step(ident, 'begin')
        self.step(ident, 'observe', result='account_not_found')
        with self.assertRaisesRegex(ValueError, 'Signup already attempted'):
            self.step(ident, 'begin')

    def test_message_cannot_be_reused_for_another_attempt(self):
        first = self.pending()
        self.step(first, 'verify-begin', **self.mail())
        self.step(first, 'observe', result='authenticated')
        second = self.pending()
        with self.assertRaisesRegex(ValueError, 'already used'):
            self.step(second, 'verify-begin', **self.mail())

    def test_permission_is_separate_and_site_updates_preserve_it(self):
        self.settings.save(dict(kind='site', url=SITE, allow_login=True, allow_signup=True))
        self.assertTrue(self.settings.public()['sites'][SITE]['verification']['enabled'])
        for change in [dict(enabled='yes'), dict(senders=''), dict(origins='https://evil.invalid/token'),
                       dict(mailbox='not-email')]:
            with self.assertRaises(ValueError):
                self.policy(**change)
        self.policy(enabled=False)
        ident = self.pending()
        with self.assertRaises(ValueError):
            self.step(ident, 'verify-begin', **self.mail())

    def legacy(self):
        data = self.settings.read()
        data.pop('schema_version')
        data.pop('account_flows')
        with closing(sqlite3.connect(self.settings.path)) as db:
            db.execute('UPDATE private SET value=? WHERE id=1',
                       (self.settings.crypt(json.dumps(data).encode()),))
            db.commit()
        return data

    def test_private_migration_backup_idempotent_and_preserves_credentials(self):
        old = self.legacy()
        self.settings.save(dict(kind='signup', email=MAIL))
        backups = list((self.root/'backups').glob('private-schema-1-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as db:
            value = db.execute('SELECT value FROM private').fetchone()[0]
            self.assertEqual(json.loads(self.settings.crypt(value, True)), old)
        self.assertEqual(self.settings.read()['schema_version'], 2)
        self.settings.save(dict(kind='signup', email=MAIL))
        self.assertEqual(list((self.root/'backups').glob('private-schema-1-*.sqlite3')), backups)

    def test_migration_failure_and_future_version_do_not_write(self):
        old = self.legacy()
        with patch.object(Path, 'mkdir', side_effect=OSError('Synthetic backup failure')):
            with self.assertRaises(OSError):
                self.settings.save(dict(kind='signup', email=MAIL))
        self.assertEqual(self.settings.read(), old)
        self.settings.save(dict(kind='signup', email=MAIL))
        def future(data):
            data['schema_version'] = 99
        self.settings.change(future)
        before = self.settings.path.read_bytes()
        with self.assertRaises(ValueError):
            self.settings.save(dict(kind='signup', email=MAIL))
        self.assertEqual(before, self.settings.path.read_bytes())


if __name__ == '__main__':
    unittest.main()
