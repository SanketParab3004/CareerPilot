"""Synthetic observations for tests only; never a production evidence generator."""
import copy
from datetime import datetime, timezone

def observed(answers):
    return [dict(a, confirmed=True, page_evidence='Synthetic fixture displays this exact value') for a in answers]

def preflight(ws, jid, aid, **changes):
    job = ws.read()['jobs'][jid]
    payload = dict(op='pre-submit-check',job_id=jid,authorization_id=aid,checked_at=datetime.now(timezone.utc).isoformat(),
        page_url=job['checkpoint']['page_url'], job_url=job['url'],company=job['company'],title=job['title'],
        answers=job['checkpoint']['answers'],uploads=job['checkpoint'].get('uploads',[]),errors=[],required_complete=True,
        submit_visible=True,evidence='Synthetic review page only; no live browser')
    payload.update(changes)
    return ws.mutate(payload)

def receipt(ws,jid,**changes):
    job=ws.read()['jobs'][jid]
    payload=dict(op='confirmation-record',job_id=jid,observed_at=datetime.now(timezone.utc).isoformat(),
        page_url=job['checkpoint']['page_url'],page_text='Synthetic application received',matched_job_evidence='Synthetic exact job receipt',
        screenshot_unavailable_reason='Synthetic text fixture',email_unavailable_reason='No mailbox in tests')
    payload.update(changes)
    return ws.mutate(payload)['confirmation_id']

def verification_payload(ws,jid,sha,content,pointer='/fixture_document'):
    return dict(op='document-verify',job_id=jid,sha256=sha,expected_text=content,
        claims=[dict(kind='fact',text=content,sources=[dict(kind='profile',pointer=pointer,quote=content)])],headings=[],dates=[],
        visual=dict(reading_order=True,contact_details=True,dates=True,headings=True,tables=True,no_clipping=True,page_count=1,evidence='Synthetic plain text file inspected'),
        requirements=[dict(quote=ws.read()['jobs'][jid]['description'],status='gap',reason='Synthetic gap; no fabricated experience')],
        requirements_review='Entire synthetic posting reviewed',keywords=[],
        critique=dict(clarity='Readable synthetic text',relevance='Synthetic fixture only',evidence='Profile fixture',gaps='No invented skills',improvements='None for fixture',findings=[]))

def approve_text(ws,jid,doc,content):
    profile=copy.deepcopy(ws.read()['profile']);profile['fixture_document']=content
    ws.mutate(dict(op='profile-save',profile=profile))
    verified=ws.mutate(verification_payload(ws,jid,doc['sha256'],content))
    ws.mutate(dict(op='document-approve',job_id=jid,sha256=doc['sha256'],verification_id=verified['verification_id'],candidate_instruction='Synthetic candidate approves this exact document and critique'))

def upload(doc):
    return dict(sha256=doc['sha256'],filename=doc['original_name'],confirmed=True,page_evidence='Synthetic fixture displays this uploaded file')
