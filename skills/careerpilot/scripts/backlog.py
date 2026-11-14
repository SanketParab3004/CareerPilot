"""Stage-one canonical backlog operations. No network or browser execution."""
import copy
import re
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

TYPES = {'login_account', 'candidate_answer', 'video_file', 'email_send',
         'form_unreadable', 'input_rejected', 'session_interrupted', 'needs_review'}
FINAL = {'Submitted', 'Interview', 'Rejected', 'Offer', 'Withdrawn', 'Expired'}
OPS = {'blocker-add', 'blocker-resolve', 'question-add', 'answer-save',
       'login-session-start', 'login-session-complete', 'resume-inspect',
       'interrupt', 'freshness-record', 'deadline-set', 'handoff-draft', 'handoff-sent'}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def words(value, name):
    need(isinstance(value, str) and value.strip(), name + ' is required')
    return value.strip()

CREDENTIAL = re.compile(r'password|passcode|one.time.code|\botp\b|access.token|secret.key', re.I)

def safe_field(value):
    need(not CREDENTIAL.search(value),
         'Do not store credentials or verification codes in backlog; use encrypted settings or manual assistance')

def field_key(note):
    """Field name for a free-text unresolved note; masks credential words so the answer can be confirmed."""
    return CREDENTIAL.sub('[credential]', note)

def now():
    return datetime.now(timezone.utc)

def stamp(value):
    value = datetime.fromisoformat(words(value, 'timestamp').replace('Z', '+00:00'))
    need(value.tzinfo is not None, 'Timestamp needs a timezone')
    return value

def site(value):
    p = urlsplit(words(value, 'site'))
    need(p.scheme == 'https' and p.hostname and not p.username and not p.password
         and not p.query and not p.fragment, 'Use an exact HTTPS site/tenant URL without credentials, query or fragment')
    return f'{p.scheme}://{p.netloc.lower()}{p.path}'.rstrip('/')

def default_site(job):
    # Full posting path deliberately avoids merging unrelated tenants on one host.
    p = urlsplit(job['url'])
    return f'{p.scheme}://{p.netloc}{p.path}'.rstrip('/')

def empty():
    return {'blockers': {}, 'questions': {}, 'answers': {}, 'login_sessions': {}, 'handoffs': {}}

def add_blocker(state, job, data, ident=None):
    kind = data.get('type', 'needs_review')
    need(kind in TYPES, 'Unknown blocker type')
    owner = data.get('owner', 'candidate')
    need(owner in {'candidate', 'agent'}, 'Owner must be candidate or agent')
    deadline = data.get('deadline')
    if deadline is not None:
        deadline = stamp(deadline).isoformat()
    effort = data.get('estimated_minutes')
    need(effort is None or type(effort) is int and 0 < effort <= 1440, 'Effort must be positive minutes or null')
    ident = ident or uuid.uuid4().hex[:12]
    item = dict(id=ident, job_id=job['id'], type=kind,
        site=site(data['site']) if data.get('site') else default_site(job),
        reason=words(data.get('reason'), 'reason'), next_action=words(data.get('next_action'), 'next action'),
        owner=owner, deadline=deadline, estimated_minutes=effort,
        evidence=words(data.get('evidence', data.get('reason')), 'evidence'),
        original_text=data.get('original_text', data.get('reason')), status='open', created_at=now().isoformat())
    state['backlog']['blockers'][ident] = item
    return item

def upgrade(state):
    """Pure transformation; caller must back up and hold the write transaction."""
    state['backlog'] = empty()
    for job in state['jobs'].values():
        if job.get('checkpoint'):
            job['checkpoint_history'] = [copy.deepcopy(job['checkpoint'])]
        if job['status'] in {'Filling', 'Needs attention', 'Preparing', 'Ready for review'}:
            job['resume_required'] = True
        if job['status'] == 'Needs attention':
            add_blocker(state, job, dict(reason=job.get('blocker') or 'Legacy blocker; details unknown',
                next_action=job.get('next_action') or 'Inspect the saved blocker with the candidate',
                original_text=job.get('blocker', ''), evidence='Migrated saved blocker; type not inferred'), 'legacy-' + job['id'])
        for index, unresolved in enumerate(job.get('checkpoint', {}).get('unresolved', [])):
            qid = 'legacy-question-' + job['id'] + '-' + str(index)
            state['backlog']['questions'][qid] = dict(id=qid, job_id=job['id'],
                question=str(unresolved), context='legacy:' + job['id'], field=field_key(str(unresolved)),
                evidence='Saved unresolved checkpoint field', status='open', reusable=False)
    state['schema_version'] = 2

def open_blockers(state, jid):
    return [b for b in state['backlog']['blockers'].values() if b['job_id'] == jid and b['status'] == 'open']

def freshness_ok(job):
    f = job.get('freshness', {})
    return (f.get('open') is True and f.get('route_valid') is True
            and f.get('job_url') == job['url'] and f.get('checked_at')
            and timedelta(0) <= now() - stamp(f['checked_at']) <= timedelta(hours=24)
            and (not job.get('closing_at') or stamp(job['closing_at']) > now()))

def guard(state, job, op):
    if op in {'start', 'document-add', 'checkpoint', 'ready', 'submit-begin'}:
        need(freshness_ok(job), 'Recheck live posting and application route; record freshness before spending effort')
    if op in {'start', 'checkpoint', 'ready', 'submit-begin'}:
        need(not job.get('resume_required'), 'Inspect the live page with resume-inspect before continuing')
        need(not open_blockers(state, job['id']), 'Resolve outstanding blockers first')
        need(not any(q['job_id'] == job['id'] and q['status'] == 'open' for q in state['backlog']['questions'].values()), 'Candidate answers are outstanding')
    if op in {'ready', 'submit-begin'}:
        need(not job.get('pending_answers'), 'Checkpoint the candidate answers actually entered in the live form first')

def checkpoint_questions(state, job):
    """Preserve unknown fields in the batched list, without inventing reuse scope."""
    for value in job['checkpoint']['unresolved']:
        question = str(value)
        existing = [q for q in state['backlog']['questions'].values()
                    if q['job_id'] == job['id'] and q['question'] == question and q['status'] == 'open']
        if not existing:
            qid = uuid.uuid4().hex[:12]
            state['backlog']['questions'][qid] = dict(id=qid, job_id=job['id'], question=question,
                field=field_key(question), context='job:' + job['id'], status='open', evidence=job['checkpoint']['observation'])

def queue(state):
    b = state['backlog']
    rows = []
    def append(jid, ident, kind, reason, step, evidence, **extra):
        job = state['jobs'].get(jid)
        if not job or job['status'] in FINAL:
            return
        row = dict(id=ident, job_id=jid, title=job['title'], company=job['company'], type=kind,
            site=default_site(job), reason=reason, next_action=step, evidence=evidence,
            owner='candidate', deadline=job.get('closing_at'), estimated_minutes=None, created_at=job.get('created_at', ''))
        row.update(extra)
        if not row['deadline']:
            row['deadline'] = job.get('closing_at')
        remaining = (stamp(row['deadline']) - now()).total_seconds() if row['deadline'] else None
        row['urgency'] = 'overdue' if remaining is not None and remaining <= 0 else 'due_soon' if remaining is not None and remaining <= 172800 else 'normal'
        row['priority_reason'] = ('Deadline passed; verify before further effort' if row['urgency'] == 'overdue' else
            'Deadline within 48 hours' if row['urgency'] == 'due_soon' else 'Upcoming deadlines first, then oldest recorded work')
        rows.append(row)
    for item in b['blockers'].values():
        if item['status'] == 'open':
            append(item['job_id'], item['id'], item['type'], item['reason'], item['next_action'], item['evidence'],
                **{k:item[k] for k in ('site','owner','deadline','estimated_minutes','created_at')})
    for q in b['questions'].values():
        if q['status'] == 'open':
            append(q['job_id'], q['id'], 'candidate_answer', q['question'], 'Answer this question or leave it unknown', q['evidence'], context=q['context'], created_at=q.get('created_at', state['jobs'][q['job_id']].get('created_at','')))
    for h in b['handoffs'].values():
        if h['status'] == 'draft':
            append(h['job_id'], h['id'], 'email_send', 'Candidate must send this application personally',
                'Review the draft and attachments, send personally, then record the receipt', h['evidence'])
    for job in state['jobs'].values():
        if job['status'] == 'Ready for review':
            append(job['id'], 'review-'+job['id'], 'needs_review', 'Application is ready for candidate review',
                'Review answers and documents; authorize only if you want submission', 'Saved ready checkpoint')
        for index, draft in enumerate(job.get('outreach', [])):
            if draft.get('status') == 'Draft only':
                append(job['id'], 'outreach-'+job['id']+'-'+str(index), 'email_send', 'Unsent outreach draft',
                    'Review draft and separately authorize this message if you want it sent', 'Saved outreach draft; application authorization does not cover outreach')
        if job['status'] in {'Submitting', 'Submission uncertain'}:
            append(job['id'], 'uncertain-'+job['id'], 'session_interrupted', 'Submission needs reconciliation',
                'Inspect portal/receipt; never retry an ambiguous submission', job['status'])
        elif job.get('resume_required') and not open_blockers(state, job['id']):
            append(job['id'], 'resume-'+job['id'], 'session_interrupted', 'Live page inspection required',
                'Ask the agent to inspect the live page and reconcile the checkpoint', 'Saved recovery gate', owner='agent')
        elif job['status'] == 'Filling':
            append(job['id'], 'inflight-'+job['id'], 'session_interrupted', 'Form run is in progress or was interrupted',
                'On a new agent session, record interrupt and inspect the live page before continuing', 'Saved Filling status and checkpoint', owner='agent')
        if job.get('closing_at') and job['status'] not in FINAL:
            append(job['id'], 'deadline-'+job['id'], 'deadline', 'Recorded application closing date',
                'Recheck the posting and route before continuing', job.get('closing_evidence', 'Saved deadline'), owner='agent')
    rows.sort(key=lambda r: ({'overdue':0,'due_soon':1,'normal':2}[r['urgency']], r['deadline'] or '9999', r.get('created_at',''), r['id']))
    return rows

def apply(ws, state, d):
    op = d['op']; b = state['backlog']
    if op == 'login-session-start':
        tenant = site(d.get('site'))
        ids = sorted({x['job_id'] for x in b['blockers'].values() if x['status'] == 'open' and x['type'] == 'login_account' and x['site'] == tenant and state['jobs'][x['job_id']]['status'] not in FINAL | {'Submitting','Submission uncertain'}})
        need(ids, 'No blocked login jobs for this exact site/tenant')
        for existing in b['login_sessions'].values():
            if existing['site'] == tenant and existing['status'] == 'waiting':
                return existing  # Frozen scope; never add newly discovered jobs implicitly.
        sid = uuid.uuid4().hex[:12]
        b['login_sessions'][sid] = dict(id=sid, site=tenant, job_ids=ids, status='waiting', created_at=now().isoformat())
        return b['login_sessions'][sid]
    if op == 'login-session-complete':
        session = b['login_sessions'].get(d.get('session_id'))
        need(session and session['status'] == 'waiting', 'Unknown or completed login session')
        evidence = words(d.get('evidence'), 'candidate completion evidence')
        session.update(status='inspection_pending', evidence=evidence)
        for jid in session['job_ids']:
            job = state['jobs'][jid]
            if job['status'] in FINAL | {'Submitting','Submission uncertain'}:
                continue
            for item in open_blockers(state, jid):
                if item['type'] == 'login_account' and item['site'] == session['site']:
                    item.update(status='resolved', resolution=evidence)
            job['resume_required'] = True
            if not open_blockers(state, jid):
                job['status'] = 'Preparing'
        return dict(session, next_action='Inspect each live form now, then resume under existing permissions; do not submit without a valid grant')
    if op == 'answer-save':
        q = b['questions'].get(d.get('question_id'))
        need(q is not None and q['status'] == 'open', 'Unknown or answered question')
        need(state['jobs'][q['job_id']]['status'] not in FINAL | {'Submitting','Submission uncertain'}, 'Cannot change submitted or uncertain applications')
        value = words(d.get('value'), 'candidate answer')
        evidence = words(d.get('evidence'), 'actual candidate statement')
        reuse = d.get('reuse', False)
        need(type(reuse) is bool, 'reuse must be boolean')
        aid = uuid.uuid4().hex[:12]
        targets = [x for x in b['questions'].values() if x['status'] == 'open' and state['jobs'][x['job_id']]['status'] not in FINAL | {'Submitting','Submission uncertain'} and
            (x['id'] == q['id'] or reuse and x['question'] == q['question'] and x['context'] == q['context'])]
        need(all(state['jobs'][x['job_id']]['status'] not in FINAL | {'Submitting','Submission uncertain'} for x in targets), 'Cannot change submitted or uncertain applications')
        b['answers'][aid] = dict(id=aid, question=q['question'], context=q['context'], value=value, evidence=evidence,
            reusable=reuse, recorded_at=now().isoformat())
        for x in targets:
            x.update(status='answered', answer_id=aid)
            job = state['jobs'][x['job_id']]
            job.setdefault('pending_answers', {})[x['field']] = dict(value=value, source='candidate answer '+aid)
            job['review'] = None
            job['resume_required'] = True
            if job['status'] == 'Ready for review': job['status'] = 'Preparing'
        return {'answer_id':aid, 'question_ids':[x['id'] for x in targets], 'next_action':'Inspect each form and checkpoint the applied answers; saved answers do not prove browser entry'}
    job = state['jobs'].get(d.get('job_id'))
    need(job is not None, 'Unknown job_id')
    jid = job['id']
    if op == 'interrupt':
        evidence = words(d.get('evidence'), 'interruption evidence')
        need(job['status'] not in FINAL, 'Application is finished')
        if job['status'] in {'Submitting', 'Submission uncertain'}:
            job['status'] = 'Submission uncertain'
            job['notes'].append({'at':now().isoformat(), 'text':evidence, 'kind':'uncertain'})
        else:
            job['resume_required'] = True
            add_blocker(state, job, dict(type='session_interrupted', reason=evidence, owner='agent', next_action='Inspect live form before resuming'))
            job['status'] = 'Needs attention'
    elif op == 'resume-inspect':
        need(job['status'] not in FINAL | {'Submitting','Submission uncertain'}, 'Reconcile submission with resolve; do not resume')
        from toolkit import url
        page = url(d.get('page_url'))
        evidence = words(d.get('evidence'), 'live page evidence')
        need(d.get('result') in {'safe', 'uncertain'}, 'Inspection result must be safe or uncertain')
        checked = stamp(d.get('checked_at'))
        need(timedelta(0) <= now()-checked <= timedelta(minutes=15), 'Live inspection must be within 15 minutes')
        job.setdefault('inspections', []).append(dict(page_url=page, evidence=evidence, result=d['result'], checked_at=checked.isoformat()))
        job['resume_required'] = d['result'] != 'safe'
        if d['result'] == 'safe':
            need(freshness_ok(job), 'Recheck posting and route before resume')
            need(urlsplit(page).netloc == urlsplit(job['freshness']['route_url']).netloc, 'Live page differs from verified route; recheck destination')
            for item in open_blockers(state, jid):
                if item['type'] == 'session_interrupted': item.update(status='resolved', resolution=evidence)
            if not open_blockers(state, jid):
                if job['status'] == 'Needs attention': job['status'] = 'Preparing'
                job['blocker'] = ''
                job['next_action'] = ''
                for assistance in state.get('assistance', {}).values():
                    if assistance['job_id'] == jid and assistance['status'] == 'open':
                        assistance.update(status='resolved', resolved_at=now().isoformat())
        else:
            job['status'] = 'Needs attention'
            add_blocker(state, job, dict(type='session_interrupted', reason='Form state uncertain: '+evidence,
                next_action='Inspect live state with candidate; do not replay saved actions'))
    else:
        need(job['status'] not in FINAL | {'Submitting','Submission uncertain'}, 'Cannot change finished or uncertain application')
        if op == 'blocker-add':
            item = add_blocker(state, job, d)
            job.update(status='Needs attention', resume_required=True)
            return {'blocker_id':item['id'], 'job_id':jid}
        elif op == 'blocker-resolve':
            item = b['blockers'].get(d.get('blocker_id'))
            need(item and item['job_id'] == jid and item['status'] == 'open', 'Unknown or resolved blocker')
            item.update(status='resolved', resolution=words(d.get('evidence'), 'resolution evidence'))
            job['resume_required'] = True
        elif op == 'question-add':
            question = words(d.get('question'), 'question'); context = words(d.get('context'), 'explicit question context')
            safe_field(question); safe_field(words(d.get('field'), 'field'))
            qid = uuid.uuid4().hex[:12]
            q = dict(id=qid, job_id=jid, question=question, context=context, field=words(d.get('field'), 'field'),
                evidence=words(d.get('evidence'), 'form evidence'), status='open', created_at=now().isoformat())
            b['questions'][qid] = q
            answers = [a for a in b['answers'].values() if a['reusable'] and a['question'] == question and a['context'] == context]
            if answers:
                answer = answers[-1]
                q.update(status='answered', answer_id=answer['id'])
                job.setdefault('pending_answers', {})[q['field']] = dict(value=answer['value'], source='candidate answer '+answer['id'])
            job.update(review=None, resume_required=True)
            if job['status'] == 'Ready for review': job['status'] = 'Preparing'
            return {'question_id':qid}
        elif op == 'deadline-set':
            job['closing_at'] = stamp(d['closing_at']).isoformat() if d.get('closing_at') else None
            job['closing_evidence'] = words(d.get('evidence'), 'closing date source evidence')
        elif op == 'freshness-record':
            from toolkit import url
            checked = stamp(d.get('checked_at'))
            need(timedelta(0) <= now()-checked <= timedelta(hours=24), 'Freshness observation must be within 24 hours')
            need(type(d.get('open')) is bool and type(d.get('route_valid')) is bool, 'Open and route_valid must be booleans')
            job['freshness'] = dict(job_url=job['url'], route_url=url(d.get('route_url')), open=d['open'], route_valid=d['route_valid'],
                checked_at=checked.isoformat(), evidence=words(d.get('evidence'), 'live posting and route evidence'))
        elif op == 'handoff-draft':
            import document_quality
            document_quality.guard(ws, state, job)
            need(freshness_ok(job), 'Recheck posting and route before preparing handoff')
            need(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', words(d.get('recipient'), 'recipient')), 'Use the published application email address')
            hid = uuid.uuid4().hex[:12]
            b['handoffs'][hid] = dict(id=hid, job_id=jid, recipient=words(d.get('recipient'), 'recipient'),
                subject=words(d.get('subject'), 'subject'), body=words(d.get('body'), 'draft body'),
                evidence=words(d.get('evidence'), 'candidate-only application route evidence'),
                documents=copy.deepcopy(job['documents']), status='draft', created_at=now().isoformat())
            return {'handoff_id':hid, 'status':'Draft only; candidate must send'}
        elif op == 'handoff-sent':
            h = b['handoffs'].get(d.get('handoff_id'))
            need(h and h['job_id'] == jid and h['status'] == 'draft', 'Unknown or already sent handoff')
            evidence = words(d.get('evidence'), 'candidate sent receipt or statement')
            sent = stamp(d.get('sent_at')); need(sent <= now(), 'Sent time cannot be in the future')
            need(d.get('candidate_confirmed') is True, 'Candidate must confirm personally sending this application')
            h.update(status='sent', sent_at=sent.isoformat(), sent_evidence=evidence)
            job['status'] = 'Submitted'
            job['notes'].append(dict(at=now().isoformat(), kind='user-reported', text=evidence))
    job['updated_at'] = now().isoformat()
    return {'job_id':jid, 'status':job['status']}
