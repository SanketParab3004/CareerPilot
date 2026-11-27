"""Job-specific document evidence and review gates. No authoring or network client."""
import copy
import difflib
import json
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from backlog import need, words, now, safe_field

OPS = {'document-rules', 'document-verify', 'document-approve', 'document-exception',
       'document-attach-check', 'positioning-save'}
HEADINGS = {'summary','professional summary','profile','experience','work experience','employment',
            'education','skills','technical skills','projects','certifications','awards','publications',
            'languages','volunteering','interests','contact','references','cover letter'}

def empty():
    return {'rules': {'page_limit': None, 'required_sections': []}, 'rules_revision': 0,
            'versions': {}, 'exceptions': {}, 'variants': {}}

def norm(value):
    return ' '.join(value.split())

def contains_keyword(text, keyword):
    """Literal, case-insensitive phrase match; not a skill-equivalence judgment."""
    phrase = norm(keyword).casefold()
    if not phrase:
        return False
    # Keep C/C++/C# and Java/JavaScript distinct; allow punctuation around a skill.
    return re.search(r'(?<![\w+#])' + re.escape(phrase) + r'(?![\w+#])',
                     norm(text).casefold()) is not None


def current(state, jid, sha):
    item = next((d for d in state['jobs'][jid]['documents'] if d['sha256'] == sha), None)
    need(item is not None, 'Document is not registered to this job')
    return item

def path_for(ws, doc):
    from toolkit import file_digest
    path = (ws.root / doc['path']).resolve()
    need(path.is_relative_to(ws.root) and path.is_file(), 'Document missing or outside workspace')
    need(file_digest(path) == doc['sha256'], 'Document bytes changed; register a new version')
    return path

def extract(path):
    from import_profile import extract as imported
    need(path.suffix.lower() in {'.pdf', '.docx', '.txt', '.md'},
         'Final-file parse supports TXT/MD/DOCX and optional pypdf; export HTML to a supported final file')
    try:
        result = imported(path.name, path.read_bytes())
    except ValueError:
        raise
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        raise ValueError('Final file cannot be parsed; export a valid document and verify again') from exc
    need(not result['warnings'], 'Extraction incomplete: ' + '; '.join(result['warnings']))
    tables = 0
    if path.suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            tables = len(list(root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl')))
    return dict(text=result['text'], tables=tables,
                pages=len(result['pages']) if 'pages' in result else None)

def sources(ws, state, refs):
    """Validate actual leaf facts or immutable imported text; semantic review is separate."""
    need(isinstance(refs, list) and refs, 'Every factual claim needs source references')
    checked = []
    for ref in refs:
        need(isinstance(ref, dict), 'Invalid source reference')
        quote = words(ref.get('quote'), 'source quote')
        if ref.get('kind') == 'profile':
            pointer = words(ref.get('pointer'), 'profile JSON pointer')
            safe_field(pointer)
            need(pointer.startswith('/'), 'Use a profile JSON pointer beginning with /')
            value = state['profile']
            try:
                for key in pointer[1:].split('/'):
                    key = key.replace('~1', '/').replace('~0', '~')
                    value = value[int(key)] if isinstance(value, list) else value[key]
            except (KeyError, ValueError, TypeError, IndexError):
                raise ValueError('Profile source does not exist')
            need(isinstance(value, (str, int, float)) and not isinstance(value, bool), 'Reference a concrete profile leaf fact')
            need(norm(quote) in norm(str(value)), 'Source quote is absent from the profile fact')
            checked.append(dict(ref, fact=copy.deepcopy(value)))
        elif ref.get('kind') == 'import':
            from toolkit import file_digest
            path = (ws.root / words(ref.get('path'), 'import path')).resolve()
            need(path.is_relative_to((ws.root / 'imports').resolve()) and path.is_file(), 'Use workspace import evidence')
            need(file_digest(path) == ref.get('sha256'), 'Imported source hash changed')
            evidence = json.loads(path.read_text(encoding='utf-8'))
            index = ref.get('document_index')
            need(type(index) is int and 0 <= index < len(evidence.get('documents', [])), 'Invalid imported document index')
            content = evidence['documents'][index].get('text', '')
            need(norm(quote) in norm(content), 'Quote absent from imported text; reference reviewed profile facts for structured exports')
            checked.append(copy.deepcopy(ref))
        else:
            raise ValueError('Source kind must be profile or import')
    return checked

def key(jid, sha):
    return jid + ':' + sha

def register(state, job, doc):
    q = state['document_quality']; ident = key(job['id'], doc['sha256'])
    if ident not in q['versions']:
        previous = [v for v in q['versions'].values() if v['job_id'] == job['id'] and v['kind'] == doc['kind']]
        q['versions'][ident] = dict(id=ident, job_id=job['id'], **copy.deepcopy(doc),
            created_at=now().isoformat(), previous_id=previous[-1]['id'] if previous else None,
            verification=None, approval=None, legacy=False)
    return q['versions'][ident]

def upgrade(state):
    state['document_quality'] = empty()
    for job in state['jobs'].values():
        for doc in job['documents']:
            register(state, job, doc)['legacy'] = True
    state['application_quality'] = {'fields': {}, 'failures': [], 'playbook_notes': []}
    state['schema_version'] = 5

def verification_token(state, job):
    from toolkit import digest
    return digest({'profile_revision':state['profile_revision'], 'job':[job['url'],job['title'],job['company'],job['description']],
                   'rules_revision':state['document_quality']['rules_revision']})

def checked_version(ws, state, job, sha):
    doc = current(state, job['id'], sha); path_for(ws, doc)
    version = state['document_quality']['versions'][key(job['id'], sha)]
    v = version.get('verification')
    need(v and v['token'] == verification_token(state, job), 'Document needs current claim, tailoring and parse verification')
    for claim in v['claims']:
        if claim['kind'] == 'fact': sources(ws, state, claim['sources'])
    need(version.get('approval') and version['approval']['verification_id'] == v['id'], 'Candidate must approve the recruiter-reviewed document')
    origin = next(x for x in state['document_quality']['versions'].values() if x['sha256'] == sha)
    if origin['job_id'] != job['id']:
        exception = state['document_quality']['exceptions'].get(key(job['id'], sha))
        need(exception and exception['verification_id'] == v['id'], 'Document also belongs to another job; candidate must approve an exact-job exception')
    return version

def guard(ws, state, job):
    for doc in job['documents']: checked_version(ws, state, job, doc['sha256'])

def apply(ws, state, d):
    op = d['op']; q = state['document_quality']
    if op == 'document-rules':
        rules = d.get('rules'); need(isinstance(rules, dict) and set(rules) <= {'page_limit','required_sections'}, 'Unknown document rule')
        rules = dict(q['rules'], **rules)
        need(rules['page_limit'] is None or type(rules['page_limit']) is int and 1 <= rules['page_limit'] <= 100, 'Page limit must be 1–100 or null')
        need(isinstance(rules['required_sections'], list), 'Sections must be a list')
        rules['required_sections'] = [words(s, 'section') for s in rules['required_sections']]
        instruction = words(d.get('candidate_instruction'), 'candidate rules instruction')
        q['rules_history'] = q.get('rules_history', []) + [dict(rules=copy.deepcopy(rules), instruction=instruction, at=now().isoformat())]
        q['rules'] = rules; q['rules_revision'] += 1
        return {'rules':rules, 'note':'No content is truncated; violations block approval'}
    if op == 'positioning-save':
        role = words(d.get('role_family'), 'role family'); label = words(d.get('label'), 'variant label')
        focus = d.get('focus'); need(isinstance(focus, list) and focus, 'Supply sourced focus points')
        checked = []
        for item in focus:
            point = words(item.get('text'), 'focus text'); refs = sources(ws, state, item.get('sources'))
            need(any(norm(point) in norm(r['quote']) for r in refs), 'Variant focus must quote supported facts; no invented skills')
            checked.append(dict(text=point, sources=refs))
        ident = uuid.uuid4().hex[:12]
        q['variants'][ident] = dict(id=ident, role_family=role, label=label, focus=checked,
            candidate_instruction=words(d.get('candidate_instruction'), 'candidate variant approval'), profile_revision=state['profile_revision'])
        return {'variant_id':ident}
    job = state['jobs'].get(d.get('job_id')); need(job is not None, 'Unknown job_id')
    need(job['status'] not in {'Submitted','Interview','Rejected','Offer','Withdrawn','Expired','Submitting','Submission uncertain'}, 'Cannot change finished or uncertain documents')
    sha = words(d.get('sha256'), 'document hash'); doc = current(state, job['id'], sha)
    path = path_for(ws, doc); version = q['versions'][key(job['id'], sha)]
    if op == 'document-verify':
        parsed = extract(path); content = parsed['text']
        expected = words(d.get('expected_text'), 'expected final reading order text')
        need(norm(content) == norm(expected), 'Extracted text differs from expected content or reading order')
        claims = d.get('claims'); need(isinstance(claims, list) and claims, 'Supply a complete claim manifest')
        need(norm(' '.join(words(c.get('text'), 'claim text') for c in claims)) == norm(content), 'Manifest must cover all final text in reading order')
        checked = []
        for c in claims:
            kind = c.get('kind'); need(kind in {'fact','heading','nonfactual'}, 'Unknown claim classification')
            entry = dict(kind=kind, text=c['text'])
            if kind == 'fact':
                entry['sources'] = sources(ws, state, c.get('sources'))
                numbers = re.findall(r'\d+(?:[.,]\d+)*', c['text'])
                source_numbers = re.findall(r'\d+(?:[.,]\d+)*', ' '.join(r['quote'] for r in entry['sources']))
                need(all(n in source_numbers for n in numbers), 'Claim contains an unsupported date or metric')
                if not any(norm(c['text']) in norm(r['quote']) for r in entry['sources']):
                    entry['semantic_review'] = words(c.get('semantic_review'), 'Explain why every part of the paraphrase is entailed, without added claims')
                    need(c.get('entailed') is True, 'Unsupported claim: remove it or obtain a real source')
            elif kind == 'heading':
                need(c['text'] in d.get('headings', []), 'Heading must appear in the reviewed headings list')
                need(c['text'].casefold() in HEADINGS or c['text'] in q['rules']['required_sections'], 'Use a sourced claim for substantive headings or candidate-configured section names')
            else:
                need(doc['kind'] != 'resume', 'Resume content must be sourced facts or headings')
                entry['rationale'] = words(c.get('rationale'), 'Explain why this text makes no factual candidate claim')
            checked.append(entry)
        headings = d.get('headings'); need(isinstance(headings, list), 'Supply observed headings')
        for h in headings: need(words(h, 'heading') in content, 'Heading missing from final text')
        for h in q['rules']['required_sections']: need(h in headings, 'Required document section missing: '+h)
        for name in ('name','email','phone'):
            value = state['profile'].get(name)
            if value and doc['kind'] == 'resume': need(norm(str(value)) in norm(content), 'Contact detail missing or altered: '+name)
        expected_dates = d.get('dates'); need(isinstance(expected_dates, list), 'Supply reviewed date strings, including an empty list if none')
        for value in expected_dates: need(words(value, 'date') in content, 'Expected date is missing')
        visible = d.get('visual'); need(isinstance(visible, dict), 'Supply rendered-file inspection')
        for field in ('reading_order','contact_details','dates','headings','tables','no_clipping'):
            need(visible.get(field) is True, 'Rendered-file check failed or missing: '+field)
        visual_evidence = words(visible.get('evidence'), 'rendered-file evidence')
        pages = parsed['pages'] if parsed['pages'] is not None else visible.get('page_count')
        need(pages is None or type(pages) is int and pages > 0, 'Invalid observed page count')
        if q['rules']['page_limit'] is not None:
            need(pages is not None and pages <= q['rules']['page_limit'], 'Page limit exceeded or page count unknown; revise with candidate, never silently cut content')
        coverage = d.get('requirements'); need(isinstance(coverage, list) and coverage, 'Supply per-job requirement coverage and gaps')
        for item in coverage:
            quote = words(item.get('quote'), 'posting requirement quote')
            need(norm(quote) in norm(job['description']), 'Requirement is not present in this posting')
            need(item.get('status') in {'covered','gap','unknown'}, 'Requirement status must be covered, gap or unknown')
            words(item.get('reason'), 'coverage reason')
            if item['status'] == 'covered':
                indexes = item.get('claim_indexes')
                need(isinstance(indexes, list) and indexes and all(type(i) is int and 0 <= i < len(checked) and checked[i]['kind'] == 'fact' for i in indexes), 'Coverage must link supported claims')
            else: need(not item.get('claim_indexes'), 'Do not portray a gap as supported experience')
        words(d.get('requirements_review'), 'Evidence that all material posting requirements were reviewed')
        keywords = d.get('keywords', [])
        for item in keywords:
            word = words(item.get('keyword'), 'keyword'); need(contains_keyword(job['description'], word), 'Keyword absent from posting')
            refs = sources(ws, state, item.get('sources'))
            need(any(contains_keyword(r['quote'], word) for r in refs), 'Do not add a keyword/skill the candidate lacks')
            need(contains_keyword(content, word), 'Keyword absent from final document')
        critique = d.get('critique'); need(isinstance(critique, dict), 'Recruiter-style critique required before approval')
        for field in ('clarity','relevance','evidence','gaps','improvements'): words(critique.get(field), 'critique '+field)
        findings = critique.get('findings'); need(isinstance(findings, list), 'Critique needs a findings list')
        for finding in findings:
            need(finding.get('severity') in {'blocker','suggestion'}, 'Unknown critique severity')
            words(finding.get('reason'), 'finding reason'); words(finding.get('evidence'), 'finding evidence')
        variant_id = d.get('variant_id')
        if variant_id:
            variant = q['variants'].get(variant_id)
            need(variant and variant['profile_revision'] == state['profile_revision'], 'Unknown or stale positioning variant')
            need(variant['role_family'] == job.get('attribution_context', {}).get('role_family'), 'Variant role family differs from this job')
            for point in variant['focus']: sources(ws, state, point['sources'])
        previous = q['versions'].get(version['previous_id'], {})
        old_text = previous.get('verification', {}).get('text', '') if previous.get('verification') else ''
        if version.get('verification'):
            version.setdefault('review_history', []).append(dict(verification=copy.deepcopy(version['verification']), approval=copy.deepcopy(version.get('approval'))))
        version['verification'] = dict(id=uuid.uuid4().hex, token=verification_token(state,job), text=content, claims=checked,
            requirements=copy.deepcopy(coverage), requirements_review=d['requirements_review'], keywords=copy.deepcopy(keywords),
            parse=dict(pages=pages,tables=parsed['tables'],visual_evidence=visual_evidence,dates=expected_dates,headings=headings),
            critique=copy.deepcopy(critique), variant_id=variant_id,
            diff='\n'.join(difflib.unified_diff(old_text.splitlines(), content.splitlines(), fromfile='previous', tofile='current', lineterm='')),
            prior_text_known=bool(previous.get('verification')), at=now().isoformat())
        version['approval'] = None
        return {'version_id':version['id'], 'verification_id':version['verification']['id'], 'diff':version['verification']['diff'], 'critique':critique}
    if op == 'document-approve':
        v = version.get('verification'); need(v and v['token'] == verification_token(state,job), 'Verify the current document first')
        need(d.get('verification_id') == v['id'], 'Approve the exact verification and critique ID reviewed by the candidate')
        need(not any(f['severity'] == 'blocker' for f in v['critique']['findings']), 'Resolve recruiter-review blockers before approval')
        version['approval'] = dict(verification_id=v['id'], candidate_instruction=words(d.get('candidate_instruction'), 'candidate document approval'), at=now().isoformat())
        return {'approved':version['id']}
    if op == 'document-exception':
        need(version.get('verification') and version.get('approval'), 'Verify and approve this job-specific document first')
        q['exceptions'][key(job['id'],sha)] = dict(job_id=job['id'],sha256=sha,verification_id=version['verification']['id'],
            candidate_instruction=words(d.get('candidate_instruction'), 'explicit approval to reuse this file for this job'),reason=words(d.get('reason'), 'exception reason'),at=now().isoformat())
        return {'exception':key(job['id'],sha)}
    checked_version(ws,state,job,sha)
    return {'job_id':job['id'], 'sha256':sha, 'path':str(path), 'allowed':True, 'note':'Use only this file for this job; inspect the page after upload'}

def variants_for(state, job):
    values = []
    for doc in job['documents']:
        v = state['document_quality']['versions'].get(key(job['id'],doc['sha256']), {}).get('verification')
        if v and v.get('variant_id'): values.append(v['variant_id'])
    return ','.join(sorted(set(values))) or 'None recorded'

def view(state):
    return state['document_quality']
