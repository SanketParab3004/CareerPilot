"""Canonical daily planning, visible quality flags and capacity controls."""
import copy
import re
import uuid
from difflib import SequenceMatcher
from datetime import timedelta
from urllib.parse import urlsplit
from learning import now, dt, date, need, text
from networking import norm

OPS={'daily-config','daily-profile-save','daily-start','daily-build','daily-prepare-begin','daily-prepared',
     'daily-decision','daily-publish','daily-notify','daily-delivery','job-identity','job-quality','contact-verify'}
SIGNALS={'scam','ghost','evergreen','repost','staffing_duplicate','eligibility','salary','location'}

def empty():return {'config':{'capacity':5},'profiles':{},'runs':{},'decisions':{},'usage':{}}

def upgrade(state):
    import networking
    state['networking']=networking.empty();state['daily']=empty()
    for job in state['jobs'].values():
        for i,contact in enumerate(job.get('contacts',[])):
            contact.setdefault('id',job['id']+'-contact-'+str(i))
            contact.setdefault('last_verified_at',contact.get('checked_at'))
            contact.setdefault('verification_evidence',contact.get('relevance','Unknown historical evidence'))
    state['schema_version']=4

def identity(data):
    need(isinstance(data,dict),'Identity must be an object')
    fields={k:text(data.get(k),k) for k in ('employer','requisition_id','employer_domain','evidence')}
    domain=fields['employer_domain'].casefold()
    need(re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}',domain) and '..' not in domain,'Use the verified employer domain, not an agency or generic ATS host')
    fields['employer_domain']=domain
    return fields

def duplicate(state, candidate):
    ident=candidate.get('identity')
    if not ident:return None
    ident=identity(ident)
    for job in state['jobs'].values():
        old=job.get('identity',{})
        if old and norm(old['employer'])==norm(ident['employer']) and old['employer_domain']==ident['employer_domain'] and old['requisition_id'].casefold()==ident['requisition_id'].casefold():
            return job
    return None

def warnings(state,job,rules=None):
    rules=rules or {};flags=copy.deepcopy(job.get('quality',{}).get('signals',[]));facts=job.get('quality',{}).get('facts',{})
    def flag(kind,reason,evidence):flags.append(dict(kind=kind,confidence='possible',reason=reason,evidence=evidence))
    description=job['description'].casefold()
    for phrase in ['upfront payment','pay a fee','send bank details','purchase equipment from']:
        if phrase in description:flag('scam','Payment or financial-information request warrants verification; not proof of fraud',phrase)
    for phrase in ['evergreen','talent pool','future opportunities']:
        if phrase in description:flag('evergreen','May be a standing talent pool rather than an immediate vacancy',phrase)
    published=dt(job.get('discovery',{}).get('published_at'))
    if published and now()-published>timedelta(days=60):flag('ghost','Posting is over 60 days old; verify availability, do not assume it is a ghost job',published.isoformat())
    employer=norm(job.get('identity',{}).get('employer') or job['company'])
    for other in state['jobs'].values():
        if other['id']==job['id']:continue
        same=employer==norm(other.get('identity',{}).get('employer') or other['company'])
        similarity=SequenceMatcher(None,norm(job['title']),norm(other['title'])).ratio()
        same_req=bool(job.get('identity')) and bool(other.get('identity')) and job['identity']['requisition_id']==other['identity']['requisition_id'] and job['identity']['employer_domain']==other['identity']['employer_domain']
        if same and (similarity>=0.65 or same_req):
            kind='staffing_duplicate' if facts.get('agency') or other.get('quality',{}).get('facts',{}).get('agency') else 'repost'
            flag(kind,'Possible duplicate/repost or renamed role; compare requisition before applying',{'other_job_id':other['id'],'other_title':other['title'],'title_similarity':round(similarity,2)})
            if state['learning']['applications'].get(other['id'],{}).get('confirmed'):
                flag('repost','Repeat-application warning: same employer and similar role already has a confirmed application',{'previous_application':other['id']})
        elif not same and similarity>=0.85 and norm(job.get('location'))==norm(other.get('location')) and (facts.get('agency') or other.get('quality',{}).get('facts',{}).get('agency')):
            flag('staffing_duplicate','Similar agency listing; end-client identity is not established, so retain both jobs',{'other_job_id':other['id'],'title_similarity':round(similarity,2)})
    for observation in job.get('duplicate_observations',[]):flag('repost','Same verified employer requisition observed at another URL; retained as an alias',observation)
    locations=rules.get('locations',[])
    if locations and not any(norm(x) in norm(job.get('location')) for x in locations):flag('location','Posting location conflicts with or does not establish a match to saved locations',{'candidate_locations':locations,'posting_location':job.get('location'),'unknown_is_not_ineligible':True})
    for key,wanted in rules.get('eligibility',{}).items():
        observed=facts.get('eligibility',{}).get(key)
        if observed is None or observed!=wanted:flag('eligibility','Eligibility requires review; compare explicit candidate preference and observed posting requirement',{'field':key,'candidate_requirement':wanted,'posting_fact':observed,'source':facts.get('evidence')})
    if rules.get('minimum_salary') is not None:
        salary=facts.get('salary',{})
        if salary.get('currency')!=rules.get('currency') or salary.get('period')!=rules.get('period') or salary.get('maximum') is None:
            flag('salary','Salary comparison is unknown; do not convert currency or periods implicitly',{'candidate_rule':{k:rules.get(k) for k in ('minimum_salary','currency','period')},'posting':salary})
        elif salary['maximum']<rules['minimum_salary']:flag('salary','Published maximum salary is below candidate minimum in the same currency/period',{'candidate_minimum':rules['minimum_salary'],'posting':salary,'source':facts.get('evidence')})
    return flags

def profiles_rules(rules):
    need(isinstance(rules,dict) and set(rules)<={'locations','eligibility','minimum_salary','currency','period'},'Unknown per-search rule')
    need(isinstance(rules.get('locations',[]),list) and all(isinstance(x,str) and x for x in rules.get('locations',[])),'locations must be strings')
    need(isinstance(rules.get('eligibility',{}),dict) and all(isinstance(k,str) and isinstance(v,(str,bool)) for k,v in rules.get('eligibility',{}).items()),'Eligibility rules must contain explicit candidate-provided facts')
    if rules.get('minimum_salary') is not None:
        need(type(rules['minimum_salary']) in {int,float} and 0<=rules['minimum_salary']<1e12,'Invalid minimum salary')
        text(rules.get('currency'),'currency');text(rules.get('period'),'salary period')
    return copy.deepcopy(rules)

def view(state):
    return dict(config=state['daily']['config'],profiles=list(state['daily']['profiles'].values()),runs=list(state['daily']['runs'].values()),
                quality={jid:warnings(state,j) for jid,j in state['jobs'].items()},decisions=state['daily']['decisions'])

def apply(ws,state,d):
    daily=state['daily'];op=d['op']
    if op=='daily-config':
        capacity=d.get('capacity');need(type(capacity) is int and 1<=capacity<=5,'Daily preparation capacity must be 1–5')
        daily['config']['capacity']=capacity;return daily['config']
    if op=='daily-profile-save':
        from job_search import validate_query
        query=validate_query(d);name=text(d.get('name'),'search name');pid=d.get('profile_id') or uuid.uuid4().hex[:12]
        need(not d.get('profile_id') or pid in daily['profiles'],'Unknown saved search profile')
        limit=d.get('capacity',5);need(type(limit) is int and 1<=limit<=5,'Search capacity must be 1–5')
        daily['profiles'][pid]=dict(id=pid,name=name,query=query,rules=profiles_rules(d.get('rules',{})),capacity=limit,updated_at=now().isoformat())
        return {'profile_id':pid}
    if op=='daily-start':
        profile=daily['profiles'].get(d.get('profile_id'));need(profile is not None,'Choose a saved search profile')
        day=now().date().isoformat()
        running=next((r for r in daily['runs'].values() if r['profile_id']==profile['id'] and r['day']==day and r['status'] not in {'published'}),None)
        if running:return running
        sid=ws.apply(state,dict(op='portal-search-start',**profile['query']))['search_id'];rid=uuid.uuid4().hex[:12]
        daily['runs'][rid]=dict(id=rid,profile_id=profile['id'],profile_snapshot=copy.deepcopy(profile),day=day,search_id=sid,status='awaiting_agent',created_at=now().isoformat(),items=[],audit=[],delivery='not_requested')
        return dict(daily['runs'][rid],next_action='Host: run both primary portals, record source coverage, build digest, prepare within capacity, publish. No scheduler installed.')
    if op in {'job-identity','job-quality','contact-verify'}:
        job=state['jobs'].get(d.get('job_id'));need(job is not None,'Unknown job')
        if op=='contact-verify':
            from toolkit import url
            contact=next((c for c in job['contacts'] if c.get('id')==d.get('contact_id')),None);need(contact is not None,'Unknown saved hiring contact')
            verification=dict(at=date(d.get('verified_at')),source_url=url(d.get('source_url')),evidence=text(d.get('evidence'),'observed contact verification'))
            contact.setdefault('verification_history',[]).append(verification)
            contact.update(last_verified_at=verification['at'],verification_evidence=verification['evidence'],source_url=verification['source_url'])
            return {'contact_id':contact['id'],'last_verified_at':contact['last_verified_at']}
        if op=='job-identity':job['identity']=identity(d.get('identity'));return {'job_id':job['id']}
        facts=d.get('facts',{});signals=d.get('signals',[])
        need(isinstance(facts,dict) and set(facts)<={'agency','eligibility','salary','evidence'},'Unsupported posting facts')
        need(isinstance(signals,list),'signals must be a list')
        if facts:
            text(facts.get('evidence'),'posting fact evidence')
            need(isinstance(facts.get('eligibility',{}),dict),'Eligibility must be explicit observed fields')
            salary=facts.get('salary',{});need(isinstance(salary,dict),'Salary must be an object')
            if salary:
                need(type(salary.get('maximum')) in {int,float} and 0<=salary['maximum']<1e12,'Invalid published salary')
                text(salary.get('currency'),'salary currency');text(salary.get('period'),'salary period')
        for signal in signals:
            need(isinstance(signal,dict) and signal.get('kind') in SIGNALS,'Unknown quality flag')
            need(signal.get('confidence') in {'possible','confirmed'},'Label confidence possible or confirmed');text(signal.get('reason'),'flag reason');text(signal.get('evidence'),'flag evidence')
        job['quality']=dict(facts=facts,signals=signals,checked_at=now().isoformat());return {'job_id':job['id']}
    run=daily['runs'].get(d.get('run_id'));need(run is not None,'Unknown daily run')
    if op=='daily-build':
        need(run['status']=='awaiting_agent','Digest already built')
        search=state['searches'][run['search_id']];need(search['status'] in {'complete','partial','failed'},'Finish both required portal coverage records first')
        from job_search import rankings
        ranks=rankings(state);items=[];audit=[];rules=run['profile_snapshot']['rules']
        remaining=min(run['profile_snapshot']['capacity'],max(0,daily['config']['capacity']-len(daily['usage'].get(run['day'],[]))))
        for jid in sorted(search['job_ids'],key=lambda key:(-ranks[key]['score'],key)):
            job=state['jobs'][jid];decision=daily['decisions'].get(jid,{})
            reason=None
            if state['learning']['applications'].get(jid,{}).get('confirmed') or job['status'] in {'Submitting','Submission uncertain'}:reason='Already applied or submission uncertain; reconcile rather than repeat'
            elif decision.get('decision')=='skip':reason='Candidate skipped this job'
            elif decision.get('decision')=='snooze' and dt(decision['until'])>now():reason='Candidate snoozed this job until '+decision['until']
            elif len(items)>=min(5,remaining):reason='Daily preparation capacity reached; retained in pipeline'
            flags=warnings(state,job,rules)
            if reason:audit.append(dict(job_id=jid,reason=reason,flags=flags));continue
            items.append(dict(job_id=jid,rank=ranks[jid],flags=flags,preparation='pending',decision=decision.get('decision','pending')))
        run.update(status='preparing',items=items,audit=audit,coverage=copy.deepcopy(search['coverage']),coverage_status=search['status'])
        return run
    if op in {'daily-prepare-begin','daily-prepared','daily-decision'}:
        jid=d.get('job_id');item=next((i for i in run['items'] if i['job_id']==jid),None);need(item is not None,'Job is outside this exact digest')
        job=state['jobs'][jid]
        if op=='daily-prepare-begin':
            need(run['status']=='preparing' and item['preparation']=='pending','Job is not pending preparation')
            used=daily['usage'].setdefault(now().date().isoformat(),[])
            need(now().date().isoformat()==run['day'],'Start a new daily run for a new UTC day')
            need(len(used)<daily['config']['capacity'] and jid not in used,'Daily capacity reached or already claimed')
            if item['flags']:text(d.get('review_evidence'),'review the visible quality flags before preparation')
            from backlog import freshness_ok
            need(freshness_ok(job),'Verify the live posting and route before spending effort')
            need(not state['learning']['applications'].get(jid,{}).get('confirmed'),'Already applied')
            used.append(jid);item['preparation']='working';item['review_evidence']=d.get('review_evidence');return {'job_id':jid,'claimed':True}
        if op=='daily-prepared':
            need(item['preparation']=='working','Claim capacity before preparing')
            status=d.get('status');need(status in {'prepared','blocked'},'Choose prepared or blocked')
            if status=='prepared':
                need(job['documents'] and job.get('evaluation',{}).get('evidence'),'Register actual materials and evidence-backed evaluation before marking prepared')
                ws.fingerprint(state,job)  # Verify registered document bytes, not just metadata.
                import document_quality
                document_quality.guard(ws,state,job)
            else:
                ws.apply(state,dict(op='blocker-add',job_id=jid,type=d.get('blocker_type','needs_review'),
                    reason=text(d.get('evidence'),'actual blocker evidence'),evidence=d['evidence'],
                    next_action=d.get('next_action','Review the daily preparation blocker with the candidate')))
            item.update(preparation=status,preparation_evidence=text(d.get('evidence'),'actual preparation result'));return {'job_id':jid,'preparation':status}
        decision=d.get('decision');need(decision in {'approve','skip','snooze'},'Choose approve, skip or snooze')
        result=dict(decision=decision,at=now().isoformat(),reason=text(d.get('candidate_instruction'),'candidate decision'))
        if decision=='approve':
            # Reuse the existing reviewed-snapshot gate; a digest is never authorization.
            grant=ws.apply(state,dict(op='authorize',job_ids=[jid],user_instruction=result['reason'],expires_at=d.get('expires_at')))
            result['authorization_id']=grant['authorization_id']
        if decision=='snooze':
            until=dt(d.get('until'));need(until and until>now(),'Future timezone-aware snooze date required');result['until']=until.isoformat()
        daily['decisions'][jid]=result;item['decision']=decision;return dict(job_id=jid,**result)
    if op=='daily-publish':
        need(run['status']=='preparing','Digest is not ready to publish')
        need(all(i['preparation'] in {'prepared','blocked'} or i['decision'] in {'skip','snooze'} for i in run['items']),'Complete or explicitly block each preparation before publishing')
        run.update(status='published',published_at=now().isoformat());return {'run_id':run['id'],'status':'published','coverage_status':run['coverage_status']}
    if op=='daily-notify':
        need(run['status']=='published','Publish the dashboard digest first')
        need(d.get('candidate_instruction') and run['delivery']=='not_requested','Explicit digest delivery request required; never auto-retry ambiguous delivery')
        run['delivery']='sending';return {'run_id':run['id'],'count':len(run['items']),'coverage_status':run['coverage_status']}
    if op=='daily-delivery':
        need(run['delivery']=='sending' and d.get('status') in {'sent','uncertain'},'No pending notification delivery')
        run['delivery']=d['status'];return {'run_id':run['id'],'delivery':run['delivery']}
    raise ValueError('Unknown daily operation')

def deliver_digest(root,run_id,result):
    from private_settings import send_telegram
    from toolkit import Workspace
    try:
        send_telegram(root,f"CareerPilot daily digest {run_id}: {result['count']} jobs. Coverage: {result['coverage_status']}. Open CareerPilot Daily digest through your configured remote access to review, approve, skip or snooze. No application was submitted.")
        status='sent'
    except (ValueError,OSError):status='uncertain'
    return Workspace(root).mutate(dict(op='daily-delivery',run_id=run_id,status=status))
