"""Local, evidence-based application attribution and descriptive learning. No network."""
import copy
import hashlib
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

OPS = {'learning-attribution', 'learning-config', 'learning-outcome', 'learning-rejection',
       'learning-propose', 'learning-approve', 'learning-undo', 'learning-touch'}
CONTEXT = {'role_family', 'seniority', 'tailoring_approach', 'ats', 'referral_used', 'outreach_used'}
FACTORS = ('source', 'role_family', 'seniority', 'fit_score', 'document_versions',
           'tailoring_approach', 'posting_age_days', 'time_to_apply_minutes', 'ats', 'referral_used', 'outreach_used')
REPLIES = {'Under review', 'Assessment', 'Interview', 'Rejected', 'Offer'}
OUTCOMES = REPLIES | {'Application received', 'Withdrawn', 'Expired'}
FINAL = {'Rejected', 'Offer', 'Withdrawn', 'Expired'}
CAUTION = 'Observed correlation only, not causation. Selection, timing and unmeasured differences may explain these rates.'

def need(ok, message):
    if not ok:
        raise ValueError(message)

def text(value, name):
    need(isinstance(value, str) and 0 < len(value.strip()) <= 4000, name + ' is required (maximum 4000 characters)')
    return value.strip()

def now():
    return datetime.now(timezone.utc)

def dt(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, AttributeError, TypeError):
        return None

def date(value):
    result = dt(value)
    need(result is not None and result <= now() + timedelta(minutes=5), 'Use an actual timezone-aware date, not a future date')
    return result.isoformat()

def empty():
    return {'config': {'minimum_sample':20, 'observation_days':14, 'stale_days':14, 'silence_days':45},
            'applications':{}, 'proposals':{}, 'revision':0}

def record(state, jid):
    return state['learning']['applications'].setdefault(jid, {'job_id':jid, 'confirmed':False,
        'snapshot':None, 'outcomes':[], 'rejection_reasons':[], 'touches':[]})

def snapshot(job, applied_at, backfilled=False, documents=None):
    context = job.get('attribution_context', {})
    values = {k:context.get(k) for k in CONTEXT}
    values.update(source=job.get('source'), fit_score=job.get('evaluation', {}).get('score'),
                  document_versions=copy.deepcopy(documents if documents is not None else job.get('documents', [])))
    published, applied, started = dt(job.get('discovery', {}).get('published_at')), dt(applied_at), dt(job.get('preparation_started_at'))
    values['posting_age_days'] = (applied-published).total_seconds()/86400 if applied and published and applied >= published else None
    values['time_to_apply_minutes'] = (applied-started).total_seconds()/60 if applied and started and applied >= started else None
    missing = [k for k in FACTORS if values.get(k) is None]
    if not applied: missing.append('applied_at')
    return dict(values, applied_at=applied_at, backfilled=backfilled, incomplete=backfilled or bool(missing), missing=missing,
                captured_at=now().isoformat(), evidence=copy.deepcopy(context.get('evidence', {})),
                provenance='Saved source/fit/document hashes and preparation timestamps; context requires supplied evidence')

def confirm(state, jid, applied_at, evidence, backfilled=False, documents=None):
    app = record(state, jid); job = state['jobs'][jid]
    if not app['confirmed']:
        app['confirmed'] = True
        app['confirmation_evidence'] = evidence
        attempt = job.get('attribution_attempt')
        app['snapshot'] = copy.deepcopy(attempt) if attempt and not backfilled else snapshot(job, applied_at, backfilled, documents)
        if attempt and not backfilled:
            # Attribute at the recorded attempt time; confirmation can arrive later.
            app['snapshot']['confirmation_at'] = applied_at
    return app

def outcome(state, jid, status, occurred_at, evidence, event_id, backfilled=False):
    app = record(state, jid)
    applied=dt(app['snapshot'].get('applied_at')) if app['snapshot'] else None
    if not backfilled and applied and dt(occurred_at):
        need(dt(occurred_at)>=applied,'Outcome predates the confirmed application')
    previous=next((x for x in app['outcomes'] if x['id']==event_id),None)
    if previous:
        need(previous['status']==status and previous['occurred_at']==occurred_at and previous['evidence']==evidence,
             'Source event ID already has different outcome evidence')
        return
    app['outcomes'].append(dict(id=event_id, status=status, occurred_at=occurred_at,
        evidence=evidence, backfilled=backfilled, recorded_at=now().isoformat()))

def upgrade(state):
    state['learning'] = empty()
    for jid, job in state['jobs'].items():
        app = record(state, jid)
        # Status is historical evidence, not evidence of a new browser action.
        if job['status'] in {'Submitted','Interview','Offer','Rejected','Withdrawn'}:
            notes = [n for n in job.get('notes', []) if n.get('kind') in {'submitted','user-reported','resolve'}]
            applied = next((n['at'] for n in notes if n.get('kind') == 'submitted' and dt(n.get('at'))), None)
            confirm(state, jid, applied, 'Backfilled existing application status: '+job['status'], True)
        for message in state.get('email_tracking', {}).get('messages', {}).values():
            if message.get('job_id') == jid and message.get('review') == 'applied':
                outcome(state,jid,message['suggested_status'],message.get('received_at'),message['evidence'],'email:'+message['id'],True)
        if job['status'] in OUTCOMES and not any(o['status'] == job['status'] for o in app['outcomes']):
            # Never use updated_at (which may be an unrelated note) as outcome date.
            outcome(state,jid,job['status'],None,'Backfilled status; original outcome date unknown','legacy:'+jid,True)
    state['schema_version'] = 3

def observe(state, request):
    """Run inside the helper transaction, after a successful canonical operation."""
    op = request['op']; jid = request.get('job_id'); job = state['jobs'].get(jid)
    if op == 'job-add':
        for key in state['jobs']: record(state,key)
    if job:
        record(state,jid)
        if op in {'start','document-add'}:
            job.setdefault('preparation_started_at', now().isoformat())
        if op == 'submit-begin':
            job['attribution_attempt'] = snapshot(job, job['attempts'][-1]['at'])
        if op in {'submitted','manual-submitted','handoff-sent'} or op == 'resolve' and request.get('result') == 'submitted':
            applied = date(request['applied_at']) if request.get('applied_at') else (
                request.get('sent_at') if op == 'handoff-sent' else now().isoformat() if op == 'submitted' else None)
            docs = state['backlog']['handoffs'][request['handoff_id']]['documents'] if op == 'handoff-sent' else None
            confirm(state,jid,applied,request['evidence'],backfilled=applied is None and not job.get('attribution_attempt'),documents=docs)
        if op == 'resolve' and request.get('result') == 'not_submitted':
            job.pop('attribution_attempt',None)
        if op == 'outcome':
            occurred=date(request['occurred_at']) if request.get('occurred_at') else None
            outcome(state,jid,request['status'],occurred,request['evidence'],uuid.uuid4().hex)
    if op in {'email-record','email-apply'}:
        for item in state.get('email_tracking', {}).get('messages', {}).values():
            if item.get('review') != 'applied' or not item.get('job_id'): continue
            jid = item['job_id']; app = record(state,jid)
            if any(o['id'] == 'email:'+item['id'] for o in app['outcomes']): continue
            # A received acknowledgement establishes application existence, not the
            # time the candidate applied. Other replies alone do not create a denominator.
            if item['suggested_status'] == 'Application received':
                confirm(state,jid,None,item['evidence'],True)
            outcome(state,jid,item['suggested_status'],item['received_at'],item['evidence'],'email:'+item['id'])

def latest(app):
    dated = [o for o in app['outcomes'] if dt(o.get('occurred_at'))]
    return max(dated,key=lambda o:dt(o['occurred_at'])) if dated else (app['outcomes'][-1] if app['outcomes'] else None)

def bucket(field, value):
    if value is None: return 'Unknown'
    if field == 'document_versions':
        return ' | '.join(sorted(d['kind']+':'+d['sha256'] for d in value)) or 'No documents recorded'
    if type(value) is bool: return 'Yes' if value else 'No'
    if field == 'fit_score': return '0–44' if value < 45 else '45–74' if value < 75 else '75–100'
    if field == 'posting_age_days': return '0–1 days' if value <= 1 else '1–7 days' if value <= 7 else '7–30 days' if value <= 30 else '30+ days'
    if field == 'time_to_apply_minutes': return '<30 min' if value < 30 else '30–120 min' if value <= 120 else '120+ min'
    return str(value)

def measure(apps, minimum, as_of):
    counts = Counter(); delays=[]; delay_unknown=0
    for app in apps:
        applied = dt(app['snapshot'].get('applied_at'))
        outcomes = [o for o in app['outcomes'] if not dt(o.get('occurred_at')) or dt(o['occurred_at']) <= as_of]
        statuses = {o['status'] for o in outcomes}
        counts['responses'] += bool(statuses & REPLIES)
        counts['interviews'] += 'Interview' in statuses
        counts['offers'] += 'Offer' in statuses
        replies = [dt(o.get('occurred_at')) for o in outcomes if o['status'] in REPLIES and dt(o.get('occurred_at'))]
        if statuses & REPLIES:
            if applied and replies and min(replies) >= applied:
                delays.append((min(replies)-applied).total_seconds()/86400)
            else: delay_unknown += 1
    n=len(apps)
    return dict(n=n, **{k:counts[k] for k in ('responses','interviews','offers')},
        response_rate=counts['responses']/n if n else None, interview_rate=counts['interviews']/n if n else None,
        offer_rate=counts['offers']/n if n else None, median_reply_days=median(delays) if delays else None,
        reply_time_n=len(delays), reply_time_unknown_n=delay_unknown,
        incomplete_n=sum(a['snapshot']['incomplete'] for a in apps),
        reliability='Small sample — not yet reliable' if n < minimum else 'Minimum count met — descriptive correlation only')

def factor_value(app, field, as_of):
    if field in {'referral_used','outreach_used'} and any(t['kind']+'_used'==field and dt(t['occurred_at'])<=as_of for t in app['touches']):
        return True
    return app['snapshot'].get(field)

def analytics(state, as_of=None):
    as_of=as_of or now(); config=state['learning']['config']; minimum=config['minimum_sample']
    all_apps=list(state['learning']['applications'].values())
    apps=[a for a in all_apps if a['confirmed'] and (not dt(a['snapshot'].get('applied_at')) or dt(a['snapshot']['applied_at'])<=as_of)]
    factors={}
    for field in FACTORS:
        groups=defaultdict(list)
        for app in apps: groups[bucket(field,factor_value(app,field,as_of))].append(app)
        factors[field]=[dict(value=value,job_ids=[a['job_id'] for a in group],**measure(group,minimum,as_of)) for value,group in sorted(groups.items())]
    eligible=[a for a in apps if not a['snapshot']['incomplete'] and dt(a['snapshot'].get('applied_at')) and
              all(dt(o.get('occurred_at')) and not o['backfilled'] for o in a['outcomes']) and
              as_of-dt(a['snapshot']['applied_at'])>=timedelta(days=config['observation_days'])]
    suggestions=[]
    # Same observation-age rule for both comparison groups; still not randomized.
    for field in ('source','role_family','seniority','ats','tailoring_approach'):
        groups=defaultdict(list)
        for app in eligible: groups[bucket(field,app['snapshot'].get(field))].append(app)
        valid=[(value,group,measure(group,minimum,as_of)) for value,group in groups.items() if len(group)>=minimum and value!='Unknown']
        if len(valid)<2:continue
        valid.sort(key=lambda x:(x[2]['interview_rate'],x[0]))
        low,high=valid[0],valid[-1]
        if high[2]['interview_rate']<=low[2]['interview_rate']:continue
        kind='tailoring' if field=='tailoring_approach' else 'ranking'
        suggestions.append(dict(kind=kind,factor=field,value=high[0],comparison_value=low[0],
            adjustment=5 if kind=='ranking' else high[0],
            reason=f"{high[2]['interviews']}/{high[2]['n']} interviews versus {low[2]['interviews']}/{low[2]['n']} in {field} cohorts. Trial only; no predicted improvement.",
            evidence={'preferred':high[2],'comparison':low[2],'job_ids':[a['job_id'] for a in high[1]+low[1]],
                      'minimum_sample':minimum,'observation_days':config['observation_days']}, caution=CAUTION))
    return dict(overall=measure(apps,minimum,as_of), factors=factors, suggestions=suggestions, caution=CAUTION,
        config=copy.deepcopy(config), eligible_learning_n=len(eligible), unconfirmed_n=len(all_apps)-len(apps),
        denominator='Confirmed applications; acknowledgements excluded from substantive response rate. Each rate uses applications, not the previous funnel step.',
        observation_note='Recent applications have less time to receive replies. Undated/backfilled/incomplete records are excluded from recommendations, not descriptive totals. Referral/outreach factors include dated post-application activity and may follow a response; no causal interpretation is valid.')

def hygiene(state, as_of=None):
    as_of=as_of or now();config=state['learning']['config'];rows=[]
    for app in state['learning']['applications'].values():
        if not app['confirmed'] or state['jobs'][app['job_id']]['status'] in FINAL:continue
        applied=dt(app['snapshot'].get('applied_at')); last=latest(app)
        updated=dt(last.get('occurred_at')) if last else None
        basis=max(x for x in (applied,updated) if x) if applied or updated else None
        if not basis:continue
        age=(as_of-basis).total_seconds()/86400
        if age<config['stale_days']:continue
        replied=any(o['status'] in REPLIES for o in app['outcomes'])
        silent=(as_of-applied).total_seconds()/86400 if applied else None
        label='Awaiting further update' if replied else 'No response (threshold reached; not rejection)' if silent is not None and silent>=config['silence_days'] else 'No response yet'
        rows.append(dict(job_id=app['job_id'],label=label,days_since_update=round(age,1),
            reason=f"No recorded update for {age:.1f} days (configured check period {config['stale_days']} days).",
            evidence={'applied_at':app['snapshot'].get('applied_at'),'last_update_at':updated.isoformat() if updated else None},
            next_action='Check Gmail for this exact application using the approved read-only account; configure access first if unavailable. Do not infer rejection.'))
    return sorted(rows,key=lambda r:-r['days_since_update'])

def gaps(state):
    groups=defaultdict(list)
    for app in state['learning']['applications'].values():
        for reason in app['rejection_reasons']:
            groups[(reason['category'],reason['gap'].casefold())].append(dict(job_id=app['job_id'],**reason))
    result=[]
    for (category,gap),items in sorted(groups.items()):
        n=len({x['job_id'] for x in items})
        result.append(dict(category=category,gap=gap,n=n,recurring=n>=2,evidence=items,
            note='Employer-stated reasons, not a verified assessment of candidate ability; missing reasons are unknown.'))
    return result

def revision_key(state):
    # Ignore proposals and approval events so approvals do not invalidate themselves.
    payload={'applications':state['learning']['applications'],'config':state['learning']['config']}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def active(state):
    return [p for p in state['learning']['proposals'].values() if p['status']=='approved']

def guidance(state):
    return [dict(proposal_id=p['id'],**p['suggestion']) for p in active(state) if p['suggestion']['kind']=='tailoring']

def ranking_adjustment(state, job):
    total=0; evidence=[]
    if state['learning']['applications'].get(job['id'],{}).get('confirmed') or job['status'] in FINAL | {'Submitting','Submission uncertain'}:
        return {'boost':0,'evidence':[]}
    for p in active(state):
        s=p['suggestion']
        if s['kind']!='ranking':continue
        value=job.get('source') if s['factor']=='source' else job.get('attribution_context',{}).get(s['factor'])
        if value==s['value']:
            total+=s['adjustment'];evidence.append(dict(proposal_id=p['id'],reason=s['reason'],evidence=s['evidence'],caution=CAUTION))
    return {'boost':min(10,total),'evidence':evidence}

def weekly(state, as_of=None):
    import backlog
    as_of=as_of or now(); start=as_of-timedelta(days=7)
    events=[e for e in state['events'] if dt(e.get('at')) and start<=dt(e['at'])<=as_of]
    apps=state['learning']['applications']; stats=analytics(state,as_of); stale=hygiene(state,as_of)
    stuck=backlog.queue(state);actions=[];seen=set()
    for item in stuck:
        if item['job_id'] in seen:continue
        actions.append(dict(action=item['next_action'],reason=item['reason'],evidence=item['evidence'],job_id=item['job_id']));seen.add(item['job_id'])
        if len(actions)==3:break
    for item in stale:
        if len(actions)==3:break
        if item['job_id'] not in seen:
            actions.append(dict(action=item['next_action'],reason=item['reason'],evidence=item['evidence'],job_id=item['job_id']));seen.add(item['job_id'])
    fallbacks=[dict(action='Review incomplete application attribution with your agent',reason='Missing historical facts limit valid comparisons',evidence={'incomplete_applications':stats['overall']['incomplete_n']}),
        dict(action='Review saved fit evidence before choosing the next application',reason='Focus effort on verified candidate/job alignment',evidence={'saved_jobs':len(state['jobs'])}),
        dict(action='Confirm target roles and reusable profile answers',reason='Future applications need current candidate-confirmed facts',evidence={'profile_revision':state['profile_revision']})]
    for action in fallbacks:
        if len(actions)==3:break
        if action==fallbacks[0] and not stats['overall']['incomplete_n']:continue
        actions.append(action)
    while len(actions)<3:
        actions.append(dict(action='Save a verified posting from the required job sources',reason='More observed application evidence is needed before learning',evidence={'eligible_learning_n':stats['eligible_learning_n']}))
    results=[dict(job_id=a['job_id'],**o) for a in apps.values() for o in a['outcomes'] if dt(o.get('occurred_at')) and start<=dt(o['occurred_at'])<=as_of]
    return dict(period_start=start.isoformat(),period_end=as_of.isoformat(),done=dict(Counter(e['op'] for e in events)),
        applied_job_ids=[a['job_id'] for a in apps.values() if a['confirmed'] and dt(a['snapshot'].get('applied_at')) and start<=dt(a['snapshot']['applied_at'])<=as_of],
        worked={'dated_results':results,'supported_comparisons':stats['suggestions'],'caution':CAUTION},stuck=stuck,
        hygiene=stale,next_actions=actions,rejection_gaps=gaps(state))

def apply(state, d):
    learning=state['learning'];op=d['op']
    if op=='learning-config':
        config=copy.deepcopy(learning['config'])
        need(set(d)-{'op','config','evidence'}==set(), 'Unknown configuration field')
        changes=d.get('config');need(isinstance(changes,dict) and changes and set(changes)<=set(config),'Unknown learning settings')
        config.update(changes)
        for key,value in config.items():need(type(value) is int and 1<=value<=3650,'Settings must be positive whole numbers')
        need(config['minimum_sample']>=20,'Minimum sample cannot be below 20 per comparison group')
        need(config['observation_days']>=7,'Observation window cannot be below 7 days')
        need(config['silence_days']>=config['stale_days'],'Silence threshold must be at least the stale-check period')
        learning['config']=config;learning['config_evidence']=text(d.get('evidence'),'candidate preference');return {'config':config}
    if op=='learning-propose':
        suggestions=analytics(state)['suggestions'];created=[];key=revision_key(state)
        for suggestion in suggestions:
            duplicate=next((p for p in learning['proposals'].values() if p['data_revision']==key and p['suggestion']==suggestion and p['status'] in {'pending','approved'}),None)
            if duplicate:created.append(duplicate['id']);continue
            pid=uuid.uuid4().hex[:12];learning['proposals'][pid]=dict(id=pid,status='pending',suggestion=suggestion,data_revision=key,created_at=now().isoformat());created.append(pid)
        return {'proposal_ids':created,'reason':'Only complete, aged cohorts meeting the minimum in both groups qualify; no automatic change.'}
    if op in {'learning-approve','learning-undo'}:
        p=learning['proposals'].get(d.get('proposal_id'));need(p is not None,'Unknown proposal')
        evidence=text(d.get('candidate_instruction'),'actual candidate approval or undo instruction')
        if op=='learning-approve':
            need(p['status']=='pending','Proposal is not pending')
            need(p['data_revision']==revision_key(state),'Evidence changed; generate and review a fresh proposal')
            need(p['suggestion'] in analytics(state)['suggestions'],'Comparison no longer qualifies')
            need(not any(x['suggestion']['kind']==p['suggestion']['kind'] and x['suggestion']['factor']==p['suggestion']['factor'] for x in active(state)), 'Undo the active adjustment for this factor first')
            p.update(status='approved',approved_at=now().isoformat(),candidate_instruction=evidence)
        else:
            need(p['status']=='approved','Only an active approved adjustment can be undone')
            p.update(status='undone',undone_at=now().isoformat(),undo_instruction=evidence)
        learning['revision']+=1
        return {'proposal_id':p['id'],'status':p['status'],'effective':'Future recommendations only; historical snapshots and permissions unchanged'}
    jid=d.get('job_id');need(jid in state['jobs'],'Unknown job_id');job=state['jobs'][jid];app=record(state,jid)
    if op=='learning-touch':
        need(d.get('kind') in {'referral','outreach'},'Choose referral or outreach')
        touch=dict(id=text(d.get('event_id'),'stable source event ID'),kind=d['kind'],occurred_at=date(d.get('occurred_at')),evidence=text(d.get('evidence'),'evidence that this actually happened'))
        need(not any(t['id']==touch['id'] for t in app['touches']),'Activity already recorded')
        need(d.get('observed') is True,'Record only observed activity, never a draft or planned message')
        app['touches'].append(touch)
        return {'job_id':jid,'recorded':touch['id'],'note':'Historical evidence only; no message sent or authorization granted'}
    if op=='learning-attribution':
        fields=d.get('fields');evidence=d.get('evidence')
        need(isinstance(fields,dict) and fields and set(fields)<=CONTEXT,'Use supported attribution context fields')
        need(isinstance(evidence,dict) and set(fields)<=set(evidence),'Evidence required for each attribution field')
        for key,value in fields.items():
            text(evidence[key],key+' evidence')
            if key in {'referral_used','outreach_used'}:need(value is None or type(value) is bool,'Use true, false or null for usage')
            else:need(value is None or isinstance(value,str) and 0<len(value.strip())<=120,'Use a short label or null')
        need(not app['confirmed'],'Applied attribution is frozen; do not overwrite historical snapshots')
        need(job['status'] not in {'Submitting','Submission uncertain'},'Reconcile submission before editing attribution')
        context=job.setdefault('attribution_context',{'evidence':{}});context.update(fields);context['evidence'].update(evidence)
        return {'job_id':jid,'saved':list(fields)}
    if op=='learning-outcome':
        need(job['status'] not in {'Submitting','Submission uncertain'},'Resolve uncertain submission first')
        status=d.get('status');need(status in OUTCOMES,'Unsupported outcome')
        occurred=date(d.get('occurred_at'));evidence=text(d.get('evidence'),'outcome evidence')
        applied=dt(app['snapshot'].get('applied_at')) if app['snapshot'] else None
        need(not applied or dt(occurred)>=applied,'Outcome predates the application')
        key=text(d.get('event_id'),'stable source event ID')
        outcome(state,jid,status,occurred,evidence,key)
        # This historical recording operation does not bypass canonical outcome rules.
        return {'job_id':jid,'status_recorded':status,'canonical_status':job['status']}
    if op=='learning-rejection':
        need(any(o['status']=='Rejected' for o in app['outcomes']),'Record an evidenced rejection first')
        need(d.get('category') in {'skills','positioning','other'},'Choose skills, positioning or other')
        quote=text(d.get('stated_reason'),'employer-stated reason');source=text(d.get('evidence'),'source evidence')
        need(text(d.get('gap'),'stated gap label').casefold() in quote.casefold(),'Gap label must occur in the stated reason; do not invent a deficiency')
        need(d.get('employer_stated') is True,'Reasons must be explicitly employer-stated, never inferred')
        reason=dict(id=text(d.get('reason_id'),'stable reason ID'),category=d['category'],gap=text(d.get('gap'),'stated gap label'),stated_reason=quote,evidence=source,occurred_at=date(d.get('occurred_at')))
        need(not any(r['id']==reason['id'] for r in app['rejection_reasons']),'Reason already recorded')
        app['rejection_reasons'].append(reason);return {'job_id':jid,'reason_id':reason['id']}
    raise ValueError('Unknown learning operation')
