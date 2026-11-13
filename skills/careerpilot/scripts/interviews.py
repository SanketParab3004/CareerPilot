"""Private interview and offer records. External actions belong to the host."""
import copy
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import document_quality
from learning import need, text, now, dt

OPS = {
    'story-save', 'mock-start', 'mock-answer', 'company-brief', 'prep-pack',
    'interview-event', 'interview-note', 'interview-draft', 'salary-research',
    'offer-record', 'skill-plan',
}


def empty():
    return {key: {} for key in (
        'stories', 'mocks', 'briefs', 'packs', 'events', 'notes', 'drafts',
        'salary', 'offers', 'plans',
    )}


def timestamp(value, label):
    parsed = dt(value)
    need(parsed is not None, f'{label} needs an ISO timestamp with offset')
    return parsed


def rows(value, label):
    need(isinstance(value, list) and bool(value), f'{label} must be a nonempty list')
    return value


def fields(data, *names):
    return {name: text(data.get(name), name) for name in names}


def source(data):
    need(isinstance(data, dict), 'Source must be an object')
    result = fields(data, 'url', 'publisher', 'evidence', 'accessed_on')
    parsed = urlsplit(result['url'])
    need(parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username,
         'Use a public source URL without credentials')
    accessed = datetime.fromisoformat(result['accessed_on']).date()
    need(accessed <= now().date(), 'Source access date is in the future')
    if data.get('published_on'):
        published = datetime.fromisoformat(data['published_on']).date()
        need(published <= accessed, 'Publication date follows access date')
        result['published_on'] = published.isoformat()
    result['accessed_on'] = accessed.isoformat()
    return result


def save(records, record):
    key = uuid.uuid4().hex[:12]
    record.update(id=key, recorded_at=now().isoformat())
    records[key] = record
    return copy.deepcopy(record)


def gap_evidence(state):
    groups = defaultdict(list)
    for job_id, job in state['jobs'].items():
        for gap in job.get('evaluation', {}).get('gaps', []):
            if isinstance(gap, str) and gap.strip():
                groups[gap.strip().casefold()].append({
                    'job_id': job_id, 'kind': 'posting assessment', 'evidence': gap,
                })
        for reason in state['learning']['applications'].get(job_id, {}).get('rejection_reasons', []):
            if reason['category'] == 'skills':
                groups[reason['gap'].strip().casefold()].append({
                    'job_id': job_id, 'kind': 'employer-stated', **copy.deepcopy(reason),
                })
    for version in state['document_quality']['versions'].values():
        for item in (version.get('verification') or {}).get('requirements', []):
            if item['status'] == 'gap':
                groups[item['quote'].strip().casefold()].append({
                    'job_id': version['job_id'], 'kind': 'document requirement gap',
                    'evidence': item['reason'], 'posting_quote': item['quote'],
                })
    return dict(sorted(groups.items(), key=lambda item: (-len({r['job_id'] for r in item[1]}), item[0])))


def money(data):
    result = fields(data, 'currency', 'period', 'location')
    need(len(result['currency']) == 3 and result['currency'].isascii()
         and result['currency'].isalpha(), 'Use a three-letter currency code')
    result['currency'] = result['currency'].upper()
    need(result['period'] in {'hour', 'month', 'year'}, 'Use hour, month or year')
    for key in ('low', 'high'):
        try:
            amount = Decimal(str(data.get(key)))
        except InvalidOperation as exc:
            raise ValueError(f'{key} must be a valid amount') from exc
        need(amount.is_finite() and amount >= 0, f'{key} must be finite and nonnegative')
        result[key] = str(amount)
    need(Decimal(result['low']) <= Decimal(result['high']), 'Salary range is reversed')
    return result


def apply(ws, state, data):
    op = data['op']
    records = state['interviews']
    job_id = data.get('job_id')
    job = state['jobs'].get(job_id)
    if job_id is not None:
        need(job is not None, 'Unknown job')
    if op == 'story-save':
        story = fields(data, 'title', 'situation', 'task', 'action', 'result', 'candidate_confirmation')
        for part in ('situation', 'task', 'action', 'result'):
            refs = data.get('sources', {}).get(part)
            story.setdefault('sources', {})[part] = document_quality.sources(ws, state, refs)
        for key in ('skills', 'competencies'):
            story[key] = [text(tag, key) for tag in rows(data.get(key), key)]
        story['profile_revision'] = state['profile_revision']
        return save(records['stories'], story)
    if op == 'mock-start':
        mode = data.get('mode', 'text')
        need(mode in {'text', 'voice'}, 'Choose text or voice')
        need(mode == 'text' or data.get('host_voice_confirmed') is True, 'Voice requires host support')
        round_type = data.get('round_type')
        need(round_type in {'behavioural', 'technical', 'role-specific'}, 'Unknown interview round')
        need(round_type != 'role-specific' or job is not None, 'Role-specific practice needs a job')
        questions = [text(q, 'question') for q in rows(data.get('questions'), 'questions')]
        return save(records['mocks'], dict(job_id=job_id, mode=mode, round_type=round_type,
                                          questions=questions, attempts=[]))
    if op == 'mock-answer':
        mock = records['mocks'].get(data.get('mock_id'))
        need(mock is not None, 'Unknown mock round')
        index = data.get('question_index')
        need(type(index) is int and 0 <= index < len(mock['questions']), 'Unknown mock question')
        previous = [attempt for attempt in mock['attempts'] if attempt['question_index'] == index]
        score = data.get('score')
        need(type(score) is int and 0 <= score <= 5, 'Score must be an integer from 0 to 5')
        attempt = dict(question_index=index, attempt=len(previous)+1, score=score,
                       **fields(data, 'answer', 'feedback', 'score_reason', 'next_drill'))
        attempt['recorded_at'] = now().isoformat()
        mock['attempts'].append(attempt)
        return attempt
    if op == 'skill-plan':
        gaps = gap_evidence(state)
        plan = []
        for item in rows(data.get('steps'), 'steps'):
            step = fields(item, 'gap', 'practice', 'deliverable', 'success_check', 'target_date')
            datetime.fromisoformat(step['target_date'])
            evidence = gaps.get(step['gap'].strip().casefold())
            need(evidence, 'Plan gaps must come from saved assessments or employer feedback')
            step['evidence'] = evidence
            plan.append(step)
        return save(records['plans'], {'steps': plan})
    if op == 'salary-research':
        return save(records['salary'], dict(job_id=job_id, **money(data),
                    source=source(data.get('source')), **fields(data, 'role', 'level', 'compensation_basis')))
    need(job is not None, 'This operation requires an exact saved job')
    if op == 'company-brief':
        claims = []
        for item in rows(data.get('claims'), 'claims'):
            claims.append(dict(**fields(item, 'claim', 'relevance'), source=source(item.get('source'))))
        return save(records['briefs'], dict(job_id=job_id, company=job['company'], claims=claims))
    if op == 'prep-pack':
        app = state['learning']['applications'].get(job_id, {})
        snapshot = app.get('snapshot') or {}
        need(app.get('confirmed') and not snapshot.get('backfilled'), 'Need a confirmed application with recorded submission attribution')
        if not job.get('attribution_attempt'):
            text(data.get('submitted_versions_evidence'), 'Candidate confirmation of the recorded submitted versions')
        versions = snapshot.get('document_versions')
        need(isinstance(versions, list), 'Submitted document version history is missing')
        brief_id = data.get('brief_id')
        if brief_id is not None:
            need(records['briefs'].get(brief_id, {}).get('job_id') == job_id, 'Brief belongs to a different job')
        story_ids = data.get('story_ids', [])
        need(isinstance(story_ids, list), 'story_ids must be a list')
        for story_id in story_ids:
            story = records['stories'].get(story_id)
            need(story and story['profile_revision'] == state['profile_revision'], 'Unknown or stale story')
            for refs in story['sources'].values():
                document_quality.sources(ws, state, refs)
        return save(records['packs'], dict(
            job_id=job_id, posting={key: job[key] for key in ('title', 'company', 'url', 'description')},
            document_versions=copy.deepcopy(versions), applied_at=snapshot.get('applied_at'),
            brief_id=brief_id, story_ids=story_ids,
            submitted_versions_evidence=data.get('submitted_versions_evidence'), **fields(data, 'round', 'preparation'),
        ))
    if op == 'interview-event':
        start = timestamp(data.get('start'), 'start')
        end = timestamp(data.get('end'), 'end')
        need(end > start, 'End must follow start')
        status = data.get('status', 'planned')
        need(status in {'planned', 'confirmed', 'cancelled'}, 'Unknown event status')
        event = dict(job_id=job_id, status=status, start=start.isoformat(), end=end.isoformat(),
                     **fields(data, 'round', 'evidence'))
        minutes = data.get('reminder_minutes')
        need(minutes is None or type(minutes) is int and 0 <= minutes <= 10080, 'Invalid reminder lead time')
        event['reminder_minutes'] = minutes
        if minutes is not None:
            event['remind_at'] = (start - timedelta(minutes=minutes)).isoformat()
        for key in ('host_event_id', 'host_reminder_id'):
            if data.get(key):
                event[key] = text(data[key], key)
        return save(records['events'], event)
    if op == 'interview-note':
        event_id = data.get('event_id')
        need(records['events'].get(event_id, {}).get('job_id') == job_id, 'Choose the exact interview')
        return save(records['notes'], dict(job_id=job_id, event_id=event_id,
                    **fields(data, 'observations', 'follow_up', 'evidence')))
    if op == 'interview-draft':
        kind = data.get('kind')
        need(kind in {'thank-you', 'negotiation'}, 'Unknown draft kind')
        target = records['events' if kind == 'thank-you' else 'offers'].get(data.get('target_id'))
        need(target and target['job_id'] == job_id, 'Draft target belongs to a different job')
        return save(records['drafts'], dict(job_id=job_id, target_id=target['id'], kind=kind,
                    status='draft', **fields(data, 'recipient', 'subject', 'body')))
    if op == 'offer-record':
        offer = dict(job_id=job_id, **fields(data, 'label', 'evidence'))
        offer['base'] = money(data['base']) if data.get('base') is not None else None
        for key in ('bonus', 'equity', 'benefits', 'work_arrangement', 'conditions'):
            offer[key] = text(data[key], key) if data.get(key) is not None else None
        offer['deadline'] = timestamp(data['deadline'], 'deadline').isoformat() if data.get('deadline') else None
        return save(records['offers'], offer)
    raise ValueError('Unknown interview operation')


def view(state):
    records = copy.deepcopy(state['interviews'])
    records['gap_evidence'] = gap_evidence(state)
    records['offer_comparison'] = [
        dict(offer, company=state['jobs'][offer['job_id']]['company'],
             role=state['jobs'][offer['job_id']]['title'])
        for offer in records['offers'].values()
    ]
    return records
