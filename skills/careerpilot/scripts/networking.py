"""User-file-only connections and separately authorized referral workflow."""
import csv
import hashlib
import io
import json
import re
import uuid
import zipfile
from datetime import timedelta
from pathlib import Path
from learning import now, dt, date, need, text

OPS={'network-import','network-config','network-contact-verify','network-relation',
     'network-sequence','network-draft','network-authorize','network-send-begin',
     'network-sent','network-uncertain','network-resolve','network-state','network-dnc'}

def norm(v):return ' '.join(re.findall(r'\w+',str(v or '').casefold()))
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def empty():return {'connections':{},'imports':{},'relations':[],'sequences':{},'messages':{},'grants':{},'dnc':{},'config':{'warm_boost':True,'followup_days':7,'max_messages_30d':2}}

def load_file(path, member=None):
    from import_profile import safe_member
    path=Path(path).expanduser().resolve();need(path.is_file() and path.suffix.lower() in {'.csv','.zip'},'Supply a local CSV or LinkedIn export ZIP')
    need(path.stat().st_size<=25_000_000,'Connection export exceeds 25 MB')
    raw=path.read_bytes();source_hash=hashlib.sha256(raw).hexdigest()
    if path.suffix.lower()=='.zip':
        need(member is not None,'Select the connection CSV member explicitly')
        safe_member(member);need(Path(member).name.casefold()=='connections.csv','Select Connections.csv from the supplied LinkedIn export')
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                need(archive.namelist().count(member)==1,'Missing or duplicate selected ZIP member')
                info=archive.getinfo(member);need(info.file_size<=10_000_000,'Connections CSV exceeds 10 MB');raw=archive.read(info)
        except (zipfile.BadZipFile,KeyError,RuntimeError) as exc:raise ValueError('Invalid selected connection export') from exc
    need(len(raw)<=10_000_000,'Connections CSV exceeds 10 MB')
    try:content=raw.decode('utf-8-sig')
    except UnicodeDecodeError:raise ValueError('Convert a copy of the export to UTF-8') from None
    # LinkedIn exports can have an introductory notice before the CSV header.
    lines=content.splitlines(keepends=True);offset=0
    for index,line in enumerate(lines[:20]):
        cells=[norm(x) for x in next(csv.reader([line]))]
        if ('first name' in cells and 'last name' in cells) or 'name' in cells:
            offset=index;break
    reader=csv.DictReader(io.StringIO(''.join(lines[offset:])))
    need(reader.fieldnames and len(set(reader.fieldnames))==len(reader.fieldnames),'Distinct CSV column headers required')
    from backlog import safe_field
    for header in reader.fieldnames:safe_field(header)
    rows=[]
    for row in reader:
        need(None not in row and len(rows)<5000,'Malformed row or more than 5000 connections')
        row={norm(k):v or '' for k,v in row.items()}
        name=row.get('name') or ' '.join([row.get('first name',''),row.get('last name','')]).strip()
        need(name,'Each connection needs a name')
        profile=row.get('url') or row.get('profile url') or ''
        if profile:
            from toolkit import url
            profile=url(profile)
        rows.append(dict(name=name,company=row.get('company',''),title=row.get('position') or row.get('title',''),profile_url=profile,
            schools=[x.strip() for x in row.get('schools','').split(';') if x.strip()],
            former_employers=[x.strip() for x in row.get('former employers','').split(';') if x.strip()]))
    return rows,source_hash,raw

def matches(state,job):
    net=state['networking'];company=norm(job.get('identity',{}).get('employer') or job['company']);profile=state['profile']
    employers={norm(e.get('company') or e.get('employer')) for e in profile.get('experience',[]) if isinstance(e,dict)}-{''}
    schools={norm(e.get('school') or e.get('institution')) for e in profile.get('education',[]) if isinstance(e,dict)}-{''}
    rows=[]
    for c in net['connections'].values():
        if norm(c['company'])!=company:continue
        if c['identity_key'] in net['dnc']:continue
        stale=not dt(c.get('last_verified_at')) or now()-dt(c['last_verified_at'])>timedelta(days=90)
        reasons=[dict(type='direct_connection',confidence='possible' if stale else 'confirmed',evidence=c['source'],reason='Imported direct connection lists the target employer; current employment needs verification' if stale else 'Imported connection and recently verified employer match')]
        common=schools & {norm(x) for x in c['schools']}
        if common:reasons.append(dict(type='shared_school',confidence='possible',reason='Shared school does not establish a personal relationship',evidence={'schools':sorted(common),'connection_source':c['source'],'candidate_source':'profile.education'}))
        common=employers & {norm(x) for x in c['former_employers']}
        if common:reasons.append(dict(type='former_employer',confidence='possible',reason='Shared former employer; overlapping employment not established',evidence={'employers':sorted(common),'connection_source':c['source'],'candidate_source':'profile.experience'}))
        for relation in net['relations']:
            if relation['connection_id']==c['id']:
                reasons.append(dict(type=relation['type'],confidence='confirmed',reason='Candidate-confirmed relationship',evidence=relation['evidence']))
        rows.append(dict(connection_id=c['id'],name=c['name'],company=c['company'],reasons=reasons,last_verified_at=c.get('last_verified_at')))
    if company in employers:
        rows.append(dict(connection_id=None,name=None,company=job['company'],reasons=[dict(type='former_employer',confidence='possible',reason='Candidate has this employer in profile; identify an actual contact before outreach',evidence='profile.experience')],last_verified_at=None))
    return rows

def boost(state,job):
    paths=matches(state,job)
    eligible=job['status'] not in {'Submitting','Submission uncertain','Submitted','Interview','Rejected','Offer','Withdrawn','Expired'}
    return dict(boost=5 if paths and eligible and state['networking']['config']['warm_boost'] else 0,enabled=state['networking']['config']['warm_boost'],evidence=paths,
                reason='Optional warm-path priority, not a hiring probability. Disable in Referrals.')

def contact_key(state,seq):return state['networking']['connections'][seq['connection_id']]['identity_key']

def stop_reason(state,seq):
    net=state['networking'];key=contact_key(state,seq)
    if key in net['dnc']:return 'Do not contact: '+net['dnc'][key]['reason']
    if seq['status'] in {'replied','referred','declined'}:return 'Sequence stopped after '+seq['status']
    if state['jobs'][seq['job_id']]['status'] in {'Rejected','Withdrawn','Expired','Offer','Interview'}:return 'Application is closed or already beyond referral outreach'
    messages=[m for m in net['messages'].values() if contact_key(state,net['sequences'][m['sequence_id']])==key]
    if any(m['status'] in {'sending','uncertain'} for m in messages):return 'Reconcile the prior send; never retry an ambiguous message'
    recent=[m for m in messages if m.get('sent_at') and now()-dt(m['sent_at'])<timedelta(days=30)]
    if len(recent)>=net['config']['max_messages_30d']:return 'Contact reached the 30-day message limit'
    if recent and now()-max(dt(m['sent_at']) for m in recent)<timedelta(days=net['config']['followup_days']):return 'Wait until the follow-up interval has passed'
    if seq['timing']=='after' and not state['learning']['applications'].get(seq['job_id'],{}).get('confirmed'):return 'Apply first; this sequence is scheduled after applying'
    return ''

def summary(state):
    net=state['networking'];counts={k:sum(s['status']==k for s in net['sequences'].values()) for k in ['draft','sent','replied','referred','declined']}
    jobs={s['job_id'] for s in net['sequences'].values()}
    return dict(sequence_counts=counts,jobs_with_sequences=len(jobs),messages_sent=sum(m['status']=='sent' for m in net['messages'].values()),
        uncertain_messages=sum(m['status'] in {'sending','uncertain'} for m in net['messages'].values()),
        note='Recorded networking outcomes only; neither causation nor permission to contact.')

def view(state):
    sequences=[]
    for s in state['networking']['sequences'].values():
        sent=[dt(m['sent_at']) for m in state['networking']['messages'].values() if m['sequence_id']==s['id'] and m.get('sent_at')]
        due=(max(sent)+timedelta(days=state['networking']['config']['followup_days'])).isoformat() if sent and s['status']=='sent' else None
        sequences.append(dict(s,stop_reason=stop_reason(state,s),next_followup_at=due,
            cadence_reason='Workspace follow-up interval after the last observed sent message; sending still needs separate authorization',
            cadence_evidence={'last_sent_at':max(sent).isoformat() if sent else None,'interval_days':state['networking']['config']['followup_days']}))
    return dict(connections=list(state['networking']['connections'].values()),matches={j['id']:boost(state,j) for j in state['jobs'].values()},
        sequences=sequences,summary=summary(state))

def apply(ws,state,d):
    net=state['networking'];op=d['op']
    if op=='network-import':
        need(d.get('user_supplied') is True,'Import only a user-supplied export or CSV; no connection scraping')
        rows,sha,raw=load_file(text(d.get('path'),'local export path'),d.get('member'))
        key=digest([sha,d.get('member')])
        if key in net['imports']:return {'import_id':key,'duplicate':True,'count':0}
        folder=ws.root/'imports'/'connections';folder.mkdir(parents=True,exist_ok=True);target=folder/(key+'.csv');target.write_bytes(raw)
        for index,row in enumerate(rows):
            identity=norm(row['profile_url']) if row['profile_url'] else norm(row['name']+' '+row['company'])
            cid=digest(row['profile_url'])[:20] if row['profile_url'] else digest([key,index])[:20]
            source={'path':target.relative_to(ws.root).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),'row':index+2}
            if cid in net['connections']:
                net['connections'][cid].setdefault('import_history',[]).append(source);continue
            net['connections'][cid]=dict(row,id=cid,identity_key=digest(identity),source=source,imported_at=now().isoformat(),last_verified_at=None)
        net['imports'][key]=dict(id=key,path=target.relative_to(ws.root).as_posix(),count=len(rows),at=now().isoformat())
        return {'import_id':key,'duplicate':False,'count':len(rows)}
    if op=='network-config':
        config=dict(net['config']);changes=d.get('config');need(isinstance(changes,dict) and set(changes)<=set(config),'Unknown networking settings');config.update(changes)
        need(type(config['warm_boost']) is bool,'warm_boost must be boolean')
        need(type(config['followup_days']) is int and 3<=config['followup_days']<=365,'Follow-up interval must be 3–365 days')
        need(type(config['max_messages_30d']) is int and 1<=config['max_messages_30d']<=3,'Message limit must be 1–3 per contact per 30 days')
        net['config']=config;return config
    if op in {'network-contact-verify','network-relation','network-dnc','network-sequence'}:
        c=net['connections'].get(d.get('connection_id'));need(c is not None,'Unknown imported connection')
        if op=='network-contact-verify':
            from toolkit import url
            verified=date(d.get('verified_at'));evidence=text(d.get('evidence'),'verification evidence');source=url(d.get('source_url'))
            c.setdefault('verification_history',[]).append(dict(at=verified,evidence=evidence,source_url=source))
            c.update(last_verified_at=verified,verification_evidence=evidence,verification_url=source)
            if d.get('profile_url'):c['profile_url']=url(d['profile_url'])
            for field in ('company','title'):
                if field in d:c[field]=text(d[field],field)
            return {'connection_id':c['id'],'last_verified_at':verified}
        if op=='network-relation':
            need(d.get('type') in {'former_colleague','direct_connection'},'Only candidate-confirmed relationship types accepted')
            net['relations'].append(dict(connection_id=c['id'],type=d['type'],evidence=text(d.get('candidate_confirmation'),'actual candidate relationship confirmation')));return {'saved':True}
        if op=='network-dnc':
            need(type(d.get('enabled')) is bool,'enabled must be boolean');reason=text(d.get('reason'),'candidate instruction or opt-out evidence')
            if d['enabled']:net['dnc'][c['identity_key']]=dict(reason=reason,at=now().isoformat())
            else:net['dnc'].pop(c['identity_key'],None)
            return {'do_not_contact':d['enabled']}
        jid=d.get('job_id');need(jid in state['jobs'],'Unknown job');job=state['jobs'][jid]
        need(any(m['connection_id']==c['id'] for m in matches(state,job)),'No evidenced warm path to this employer, or do-not-contact')
        existing=next((s for s in net['sequences'].values() if s['job_id']==jid and s['connection_id']==c['id']),None)
        if existing:return existing
        applied=state['learning']['applications'].get(jid,{}).get('confirmed');closing=dt(job.get('closing_at'));urgent=closing and closing-now()<timedelta(days=2)
        timing='after' if applied or urgent else 'before'
        reason='Application is already confirmed' if applied else 'Closing date is within 48 hours; do not delay the application for a referral' if urgent else 'Ask about the referral process before applying while the posting has time; do not assume a referral is available'
        sid=uuid.uuid4().hex[:12];seq=dict(id=sid,job_id=jid,connection_id=c['id'],status='draft',timing=timing,reason=reason,evidence=matches(state,job),history=[])
        net['sequences'][sid]=seq;return seq
    if op=='network-draft':
        seq=net['sequences'].get(d.get('sequence_id'));need(seq is not None,'Unknown sequence');reason=stop_reason(state,seq)
        need(not reason or reason.startswith('Wait') or reason.startswith('Apply first'),reason)
        c=net['connections'][seq['connection_id']];job=state['jobs'][seq['job_id']];mid=uuid.uuid4().hex[:12]
        default=(f"Hi {c['name']}, following up on my earlier message about the {job['title']} opening at {job['company']}. If you are able to share how referrals work, I would appreciate it. No pressure, and thank you." if seq['status']=='sent' else
                 f"Hi {c['name']}, I saw the {job['title']} opening at {job['company']}. Would you be comfortable sharing how the referral process works for this role? No pressure if you are not the right person. Thank you.")
        body=d.get('body') or default
        net['messages'][mid]=dict(id=mid,sequence_id=seq['id'],recipient=c['profile_url'] or c['name'],body=text(body,'draft body'),status='draft',created_at=now().isoformat(),evidence=seq['evidence'])
        return net['messages'][mid]
    if op in {'network-authorize','network-send-begin','network-sent','network-uncertain','network-resolve'}:
        m=net['messages'].get(d.get('message_id'));need(m is not None,'Unknown message');seq=net['sequences'][m['sequence_id']]
        if op=='network-authorize':
            need(m['status']=='draft','Only an unsent draft can be authorized');need(not stop_reason(state,seq),stop_reason(state,seq))
            c=net['connections'][seq['connection_id']]
            need(c['profile_url'] and dt(c.get('last_verified_at')) and now()-dt(c['last_verified_at'])<=timedelta(days=90),'Verify the exact professional recipient and employer before authorizing outreach')
            need(m['recipient']==c['profile_url'],'Recipient changed; create and review a new draft')
            expires=dt(d.get('expires_at'));need(expires and expires>now(),'Future timezone-aware expiry required')
            gid=uuid.uuid4().hex[:12];net['grants'][gid]=dict(id=gid,message_id=m['id'],snapshot=digest(m),expires_at=expires.isoformat(),instruction=text(d.get('candidate_instruction'),'separate outreach authorization'),used=False);return {'authorization_id':gid}
        if op=='network-send-begin':
            need(m['status']=='draft','Message is already in flight or sent');need(not stop_reason(state,seq),stop_reason(state,seq))
            c=net['connections'][seq['connection_id']]
            need(m['recipient']==c['profile_url'] and dt(c.get('last_verified_at')) and now()-dt(c['last_verified_at'])<=timedelta(days=90),'Reverify changed or stale recipient before sending')
            g=net['grants'].get(d.get('authorization_id'));need(g and not g['used'] and g['message_id']==m['id'] and g['snapshot']==digest(m) and dt(g['expires_at'])>now(),'Valid authorization for this exact message required')
            g['used']=True;m['status']='sending';m['send_started_at']=now().isoformat();return {'message_id':m['id'],'status':'sending'}
        if op=='network-resolve':
            need(m['status'] in {'sending','uncertain'},'No uncertain message to reconcile')
            need(d.get('result') in {'sent','not_sent'},'Choose sent or not_sent based on observed evidence')
            text(d.get('evidence'),'reconciliation evidence')
            if d['result']=='not_sent':
                m.update(status='cancelled',resolution=d['evidence']);return {'message_id':m['id'],'status':'cancelled','next_action':'Create a new draft and obtain a new exact-message authorization if still appropriate'}
        else:need(m['status']=='sending','No in-flight send; do not replay ambiguous messages')
        evidence=text(d.get('evidence'),'observed delivery evidence')
        m.update(status='uncertain' if op=='network-uncertain' else 'sent',evidence_of_send=evidence)
        if m['status']=='sent':
            m['sent_at']=date(d.get('sent_at'));need(dt(m['sent_at'])>=dt(m['send_started_at'])-timedelta(minutes=5),'Sent time predates this send attempt')
            seq['status']='sent';seq['history'].append(dict(status='sent',at=m['sent_at'],evidence=evidence))
            from learning import apply as learn
            learn(state,dict(op='learning-touch',job_id=seq['job_id'],kind='outreach',event_id='network:'+m['id'],occurred_at=m['sent_at'],evidence=evidence,observed=True))
        return {'message_id':m['id'],'status':m['status']}
    if op=='network-state':
        seq=net['sequences'].get(d.get('sequence_id'));need(seq is not None,'Unknown sequence')
        target=d.get('status');need(target in {'replied','referred','declined'},'Record replied, referred or declined')
        need(seq['status'] in {'sent','replied'},'Record actual sent message before reply/referral outcomes')
        evidence=text(d.get('evidence'),'observed response');at=date(d.get('occurred_at'));seq.update(status=target);seq['history'].append(dict(status=target,at=at,evidence=evidence))
        sent=[dt(m['sent_at']) for m in net['messages'].values() if m['sequence_id']==seq['id'] and m.get('sent_at')]
        need(sent and dt(at)>=max(sent),'Response predates the recorded send')
        if target=='declined':net['dnc'][contact_key(state,seq)]=dict(reason=evidence,at=at)
        if target=='referred':
            from learning import apply as learn
            learn(state,dict(op='learning-touch',job_id=seq['job_id'],kind='referral',event_id='referral:'+seq['id'],occurred_at=at,evidence=evidence,observed=True))
        return {'sequence_id':seq['id'],'status':target}
    raise ValueError('Unknown networking operation')
