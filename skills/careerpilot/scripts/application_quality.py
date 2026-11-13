"""Observed application evidence, field memory and pre-submit guards. No browser client."""
import copy
import re
import uuid
from collections import Counter
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl
import backlog
import document_quality as documents
from backlog import need, words, now, stamp, site, safe_field

OPS = {'field-observe','field-approve','failure-record','playbook-note','pre-submit-check','confirmation-record'}
FAILURES = {'address_rejected','input_rejected','iframe_unavailable','form_unreadable','upload_rejected',
            'session_interrupted','authentication','captcha_mfa','validation','unknown'}
DOMAINS = {'workday':['myworkdayjobs.com','myworkdaysite.com'], 'greenhouse':['greenhouse.io'],
           'lever':['lever.co'], 'ashby':['ashbyhq.com'], 'icims':['icims.com'],
           'smartrecruiters':['smartrecruiters.com'], 'taleo':['taleo.net'],
           'oracle':['oraclecloud.com'], 'successfactors':['successfactors.com','successfactors.eu'],
           'generic':[]}

def detect(page):
    host = urlsplit(page).hostname or ''
    return next((name for name, domains in DOMAINS.items() if any(host == d or host.endswith('.'+d) for d in domains)), 'generic')

def normalized(value):
    return re.sub(r'[^\w]+',' ',words(value,'normalized question type').casefold()).strip()

def recent(value):
    checked = stamp(value)
    need(timedelta(0) <= now()-checked <= timedelta(minutes=5), 'Inspect the live page within five minutes')
    return checked.isoformat()

def safe_page(value):
    from toolkit import url
    page = url(value); parsed = urlsplit(page)
    need(not any(re.search(r'token|password|secret|session|code|auth', k, re.I) for k, _ in parse_qsl(parsed.query)), 'Redact credential/session query parameters')
    return page

def observe_checkpoint(ws,state,job,checkpoint):
    for answer in checkpoint['answers']:
        need(answer.get('confirmed') is True, 'A field is filled only after the page confirms the value')
        words(answer.get('page_evidence'), 'observed field value/validation evidence')
    uploads = checkpoint.get('uploads', [])
    need(isinstance(uploads,list), 'Uploads must be a list')
    for upload in uploads:
        need(upload.get('confirmed') is True, 'Upload needs visible confirmation')
        words(upload.get('page_evidence'),'visible upload evidence')
        words(upload.get('filename'),'visible attached filename')
        version = documents.checked_version(ws,state,job,upload.get('sha256'))
        need(upload['filename'] in {version['original_name'],Path(version['path']).name}, 'Visible attachment filename differs from the verified file')
    if checkpoint['complete']:
        need(sorted(x.get('sha256') for x in uploads) == sorted(x['sha256'] for x in job['documents']), 'Final form uploads differ from the registered job documents')
        need(not checkpoint.get('errors'), 'Visible form errors prevent completion')

def grant_for(ws,state,job,aid):
    grant = next((g for g in state['authorizations'] if g['id'] == aid),None)
    need(grant and not grant['revoked'] and stamp(grant['expires_at']) > now(), 'Authorization missing, expired or revoked')
    need(job['id'] not in grant['used'] and grant['fingerprints'].get(job['id']) == ws.fingerprint(state,job) == job.get('review'), 'Authorization does not cover the current reviewed job')
    return grant

def submission_guard(ws,state,job,aid):
    documents.guard(ws,state,job)
    check = job.get('pre_submit')
    need(check and check['status'] == 'passed' and check['authorization_id'] == aid, 'A successful live pre-submit check for this authorization is required')
    recent(check['checked_at'])
    need(check['fingerprint'] == ws.fingerprint(state,job), 'Form/document snapshot changed after pre-submit check')
    need(check['freshness'] == job.get('freshness'), 'Route changed since pre-submit check')
    grant_for(ws,state,job,aid)

def apply(ws,state,d):
    op=d['op']; q=state['application_quality']
    job=state['jobs'].get(d.get('job_id')); need(job is not None,'Unknown job_id')
    if op == 'confirmation-record':
        need(job['status'] in {'Submitting','Submission uncertain','Submitted'}, 'Confirmation must follow an actual attempt or candidate report')
        observed=stamp(d.get('observed_at')); need(observed <= now(), 'Confirmation cannot be future dated')
        page_text=d.get('page_text'); email=d.get('email')
        need(page_text or email,'Provide observed confirmation page text or a verified email receipt')
        record=dict(id=uuid.uuid4().hex[:12],job_id=job['id'],observed_at=observed.isoformat(),page_url=safe_page(d.get('page_url')),
                    page_text=words(page_text,'confirmation text') if page_text else None,
                    matched_job_evidence=words(d.get('matched_job_evidence'),'Evidence matching exact employer and job'),
                    attempt_snapshot=job['attempts'][-1]['snapshot'] if job['attempts'] else None)
        if email:
            need(isinstance(email,dict),'Email receipt must be an object')
            record['email']={k:words(email.get(k),'email '+k) for k in ('message_id','excerpt','source_url')}
            record['email']['source_url']=safe_page(record['email']['source_url'])
            record['email']['received_at']=stamp(email.get('received_at')).isoformat()
            need(stamp(record['email']['received_at']) <= now(),'Email date is in the future')
        if d.get('screenshot_path'):
            from toolkit import file_digest
            source=Path(d['screenshot_path']).resolve()
            need(source.is_file() and source.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and source.stat().st_size<=25_000_000,'Use an existing screenshot under 25 MB')
            sha=file_digest(source); target=ws.root/'artifacts'/'confirmations'/(sha+source.suffix.lower())
            need(target.resolve().is_relative_to(ws.root),'Screenshot path escaped workspace')
            target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(source.read_bytes())
            record.update(screenshot_path=target.relative_to(ws.root).as_posix(),screenshot_sha256=sha)
        else:
            record['screenshot_unavailable_reason']=words(d.get('screenshot_unavailable_reason'),'Why screenshot evidence is unavailable')
        if not email:record['email_unavailable_reason']=words(d.get('email_unavailable_reason'),'Why email evidence is unavailable')
        job.setdefault('confirmations',[]).append(record)
        return {'confirmation_id':record['id'],'note':'Evidence recorded only; use submitted/resolve separately'}
    need(job['status'] not in backlog.FINAL | {'Submitting','Submission uncertain'}, 'Cannot alter finished or uncertain application evidence')
    if op == 'field-observe':
        question=words(d.get('question'),'exact visible wording'); safe_field(question)
        field=words(d.get('field'),'field'); safe_field(field)
        kind=normalized(d.get('question_type')); safe_field(kind)
        context=words(d.get('context'),'explicit semantic context including jurisdiction/employer/time as relevant')
        tenant=site(d.get('site'))
        for old in q['fields'].values():
            if old['job_id']==job['id'] and old['field']==field and old['site']==tenant:
                old['superseded']=True
                if state['backlog']['questions'][old['id']]['status']=='open':
                    state['backlog']['questions'][old['id']]['status']='superseded'
        result=ws.apply(state,dict(op='question-add',job_id=job['id'],question=question,field=field,context=context,evidence=d.get('evidence')))
        ident=result['question_id']; actual=state['backlog']['questions'][ident]
        # Exact Stage 1 reuse is not enough to approve an unseen semantic type/wording.
        actual.update(status='open'); actual.pop('answer_id',None); job.get('pending_answers',{}).pop(field,None)
        prior=[x for x in q['fields'].values() if x['question_type']==kind and x['context']==context and x.get('approval') and x['profile_revision']==state['profile_revision']]
        item=dict(id=ident,job_id=job['id'],question=question,field=field,question_type=kind,context=context,
                  site=tenant,profile_revision=state['profile_revision'],approval=None,
                  previous_wording=prior[-1]['question'] if prior else None,suggested_value=prior[-1]['approval']['value'] if prior else None,
                  wording_changed=bool(prior and prior[-1]['question']!=question))
        q['fields'][ident]=item
        exact=[x for x in prior if x['question']==question and x['approval']['reuse']]
        if exact:
            approved=exact[-1]['approval']
            ws.apply(state,dict(op='answer-save',question_id=ident,value=approved['value'],evidence=approved['candidate_instruction'],reuse=False))
            item['approval']=copy.deepcopy(approved)
        return item
    if op == 'field-approve':
        item=q['fields'].get(d.get('question_id')); need(item and item['job_id']==job['id'],'Unknown observed field')
        need(item['profile_revision']==state['profile_revision'],'Profile changed; observe this question again')
        value=words(d.get('value'),'candidate answer'); instruction=words(d.get('candidate_instruction'),'candidate approval of exact wording and answer')
        reuse=d.get('reuse',False); need(type(reuse) is bool,'Reuse must be boolean')
        ws.apply(state,dict(op='answer-save',question_id=item['id'],value=value,evidence=instruction,reuse=False))
        item['approval']=dict(value=value,candidate_instruction=instruction,reuse=reuse)
        return {'question_id':item['id'],'next_action':'Inspect the live form, enter value, then record observed confirmation'}
    if op in {'failure-record','playbook-note'}:
        tenant=site(d.get('site')); step=words(d.get('step'),'step'); kind=d.get('failure_type'); need(kind in FAILURES,'Unknown failure type')
        item=dict(id=uuid.uuid4().hex[:12],job_id=job['id'],site=tenant,ats=detect(tenant),step=step,failure_type=kind,
                  evidence=words(d.get('evidence'),'observed failure evidence'),at=now().isoformat())
        if op=='playbook-note':
            item['recovery']=words(d.get('recovery'),'observed recovery'); need(d.get('verified') is True,'Recovery must be observed, not speculative')
            q['playbook_notes'].append(item)
            return item
        q['failures'].append(item)
        attempts=sum(x['job_id']==job['id'] and x['site']==tenant and x['step']==step and x['failure_type']==kind for x in q['failures'])
        handoff=kind in {'iframe_unavailable','form_unreadable','captcha_mfa','authentication','session_interrupted'} or attempts>=2 or d.get('safe_method') is False
        if handoff:
            result=ws.apply(state,dict(op='blocker-add',job_id=job['id'],site=tenant,type='form_unreadable' if kind in {'iframe_unavailable','form_unreadable'} else 'input_rejected' if kind in {'input_rejected','address_rejected','validation','upload_rejected'} else 'needs_review',
                reason=item['evidence'],next_action=words(d.get('next_action'),'manual assistance next step')))
            item['blocker_id']=result['blocker_id']
        job.pop('pre_submit',None)
        return dict(item,handoff=handoff,attempts=attempts)
    # Persist mismatches as failed checks rather than raising away the evidence.
    need(op=='pre-submit-check','Unknown quality operation')
    need(job['status']=='Ready for review','Review the form before pre-submit checking')
    check=dict(id=uuid.uuid4().hex[:12],authorization_id=words(d.get('authorization_id'),'authorization ID'),
               checked_at=recent(d.get('checked_at')),page_url=safe_page(d.get('page_url')),
               evidence=words(d.get('evidence'),'live form evidence'),status='failed',mismatches=[])
    try:
        backlog.guard(state,job,'submit-begin'); grant_for(ws,state,job,check['authorization_id']); documents.guard(ws,state,job)
        need(d.get('job_url')==job['url'] and d.get('company')==job['company'] and d.get('title')==job['title'],'Visible employer/role/job identity mismatch')
        need(urlsplit(check['page_url']).netloc==urlsplit(job['freshness']['route_url']).netloc,'Visible form destination differs from verified route')
        need(d.get('answers')==job['checkpoint']['answers'],'Visible answers differ from reviewed answers')
        need(d.get('uploads')==job['checkpoint'].get('uploads',[]),'Visible attachments differ from reviewed uploads')
        need(d.get('errors')==[] and d.get('required_complete') is True,'Visible errors or incomplete required fields')
        need(d.get('submit_visible') is True,'Final submit control must be observed')
        observe_checkpoint(ws,state,job,job['checkpoint'])
        check.update(status='passed',fingerprint=ws.fingerprint(state,job),freshness=copy.deepcopy(job['freshness']))
    except ValueError as exc:check['mismatches'].append(str(exc))
    job['pre_submit']=check;job.setdefault('pre_submit_history',[]).append(copy.deepcopy(check))
    return check

def confirmation_guard(ws,job,ident):
    record=next((x for x in job.get('confirmations',[]) if x['id']==ident),None)
    need(record is not None,'Record structured confirmation evidence before confirming submission')
    need(job['attempts'] and record['attempt_snapshot']==job['attempts'][-1]['snapshot'],'Confirmation does not match the current attempt')
    need(stamp(record['observed_at']) >= stamp(job['attempts'][-1]['at'])-timedelta(minutes=5),'Confirmation predates this attempt')
    if record.get('screenshot_path'):
        from toolkit import file_digest
        path=(ws.root/record['screenshot_path']).resolve()
        need(path.is_relative_to(ws.root) and path.is_file() and file_digest(path)==record['screenshot_sha256'],'Confirmation screenshot changed or missing')

def view(state):
    q=state['application_quality']; counts=Counter((x['site'],x['step'],x['failure_type']) for x in q['failures'])
    return dict(fields=list(q['fields'].values()),failures=q['failures'],playbook_notes=q['playbook_notes'],
        common_failures=[dict(site=k[0],step=k[1],failure_type=k[2],count=n,evidence=[x['id'] for x in q['failures'] if (x['site'],x['step'],x['failure_type'])==k]) for k,n in counts.most_common()])
