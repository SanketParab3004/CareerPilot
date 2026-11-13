import copy
import json
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from test_skill import toolkit
from quality_fixtures import preflight, receipt, observed, upload, verification_payload
import application_quality as aq
import document_quality as dq
import learning

def clock(minutes=0):
    return (datetime.now(timezone.utc)+timedelta(minutes=minutes)).isoformat()

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.ws=toolkit.Workspace(self.root/'private');self.ws.initialize();self.number=0
        self.op('profile-save',profile={'fixture_document':'SQL experience 2020–2024','skills':['SQL']})

    def tearDown(self):self.temp.cleanup()
    def op(self,op,**data):return self.ws.mutate(dict(op=op,**data))
    def job(self):
        self.number+=1
        jid=self.op('job-add',title='Synthetic Analyst',company='Fixture',description='SQL experience',source='Synthetic',url=f'https://example.invalid/jobs/{self.number}')['job_id']
        self.op('freshness-record',job_id=jid,route_url='https://example.invalid/apply',checked_at=clock(),open=True,route_valid=True,evidence='Synthetic posting and route')
        return jid
    def doc(self,jid,content='SQL experience 2020–2024',kind='resume',suffix='.txt'):
        path=self.root/('document'+suffix);path.write_text(content,encoding='utf-8')
        self.op('document-add',job_id=jid,kind=kind,path=str(path))
        return self.ws.read()['jobs'][jid]['documents'][-1]
    def verify(self,jid,doc,**changes):
        d=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2020–2024');d.update(changes)
        return self.ws.mutate(d)
    def approve(self,jid,doc,**changes):
        v=self.verify(jid,doc,**changes)
        self.op('document-approve',job_id=jid,sha256=doc['sha256'],verification_id=v['verification_id'],candidate_instruction='Synthetic exact-document approval')
        return v
    def ready(self,jid,answers=None):
        self.op('select',job_id=jid);self.op('start',job_id=jid)
        self.op('checkpoint',job_id=jid,checkpoint=dict(page_url='https://example.invalid/apply',step='Review',observation='Synthetic page',answers=observed(answers or []),uploads=[upload(d) for d in self.ws.read()['jobs'][jid]['documents']],unresolved=[],complete=True,errors=[]))
        self.op('ready',job_id=jid)
        return self.op('authorize',job_ids=[jid],expires_at=clock(60),user_instruction='Synthetic exact job approval')['authorization_id']

    def test_verified_document_parse_critique_approval_and_upload(self):
        jid=self.job();doc=self.doc(jid)
        with self.assertRaises(ValueError):self.op('document-attach-check',job_id=jid,sha256=doc['sha256'])
        v=self.approve(jid,doc)
        self.assertIn('+SQL',v['diff'])
        self.assertTrue(self.op('document-attach-check',job_id=jid,sha256=doc['sha256'])['allowed'])
        aid=self.ready(jid);self.assertEqual(preflight(self.ws,jid,aid)['status'],'passed')
        self.op('submit-begin',job_id=jid,authorization_id=aid)
        with self.assertRaises(ValueError):self.op('submitted',job_id=jid,evidence='Unsupported receipt')
        self.op('submitted',job_id=jid,evidence='Synthetic exact receipt',confirmation_id=receipt(self.ws,jid))
        self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Submitted')

    def test_claim_manifest_source_and_metric_failures(self):
        jid=self.job();doc=self.doc(jid)
        payload=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2020–2024')
        for change in [dict(claims=[]),dict(claims=[dict(kind='fact',text='SQL experience 2020–2024',sources=[])]),dict(expected_text='Experience SQL 2020–2024')]:
            with self.assertRaises(ValueError):self.ws.mutate(dict(payload,**change))
        changed=copy.deepcopy(payload);changed['claims'][0]['sources'][0]['pointer']='/missing'
        with self.assertRaises(ValueError):self.ws.mutate(changed)
        doc=self.doc(jid,'SQL experience 2010–2024')
        changed=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2010–2024')
        changed['claims'][0].update(sources=[dict(kind='profile',pointer='/fixture_document',quote='SQL experience 2020–2024')],entailed=True,semantic_review='Claimed paraphrase')
        with self.assertRaisesRegex(ValueError,'unsupported date'):self.ws.mutate(changed)

    def test_paraphrase_requires_entailed_review_and_cover_letter_complete_manifest(self):
        jid=self.job();doc=self.doc(jid,'Experience with SQL',kind='cover_letter')
        d=verification_payload(self.ws,jid,doc['sha256'],'Experience with SQL');d['claims'][0]['sources'][0]['quote']='SQL experience'
        with self.assertRaises(ValueError):self.ws.mutate(d)
        d['claims'][0].update(entailed=True,semantic_review='Reorders the same supported skill without adding seniority or metrics')
        self.ws.mutate(d)
        d['claims'][0]['text']='SQL'
        with self.assertRaises(ValueError):self.ws.mutate(d)

    def test_tailoring_gaps_keywords_and_requirement_provenance(self):
        jid=self.job();doc=self.doc(jid)
        d=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2020–2024')
        d['requirements']=[dict(quote='SQL experience',status='covered',reason='Same sourced skill',claim_indexes=[0])]
        d['keywords']=[dict(keyword='SQL',sources=[dict(kind='profile',pointer='/skills/0',quote='SQL')])]
        self.ws.mutate(d)
        for replacement in [dict(quote='Java',status='gap',reason='Not in posting'),dict(quote='SQL experience',status='covered',reason='Unsupported',claim_indexes=[])]:
            with self.assertRaises(ValueError):self.ws.mutate(dict(d,requirements=[replacement]))
        d['keywords'][0]['sources'][0]['quote']='Java'
        with self.assertRaises(ValueError):self.ws.mutate(d)

    def test_rules_do_not_truncate_and_unknown_page_count_blocks(self):
        jid=self.job();doc=self.doc(jid);original=(self.ws.root/doc['path']).read_bytes()
        self.assertIsNone(self.ws.read()['document_quality']['rules']['page_limit'])
        self.op('document-rules',rules={'page_limit':1},candidate_instruction='Synthetic page preference')
        d=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2020–2024');d['visual']['page_count']=2
        with self.assertRaises(ValueError):self.ws.mutate(d)
        d['visual']['page_count']=None
        with self.assertRaises(ValueError):self.ws.mutate(d)
        self.assertEqual((self.ws.root/doc['path']).read_bytes(),original)
        self.op('document-rules',rules={'page_limit':None,'required_sections':['Experience']},candidate_instruction='Synthetic section preference')
        with self.assertRaisesRegex(ValueError,'section missing'):self.verify(jid,doc)
        with self.assertRaises(ValueError):self.op('document-rules',rules={'page_limit':0},candidate_instruction='Bad limit')

    def test_parse_checks_contacts_dates_visual_errors_and_missing_optional_pdf(self):
        jid=self.job();doc=self.doc(jid)
        profile=self.ws.read()['profile'];profile['email']='synthetic@example.invalid';self.op('profile-save',profile=profile)
        with self.assertRaisesRegex(ValueError,'Contact detail'):self.verify(jid,doc)
        del profile['email'];self.op('profile-save',profile=profile)
        with self.assertRaisesRegex(ValueError,'date is missing'):self.verify(jid,doc,dates=['1999'])
        d=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2020–2024');d['visual']['tables']=False
        with self.assertRaises(ValueError):self.ws.mutate(d)
        path=self.root/'file.pdf';path.write_bytes(b'%PDF synthetic')
        with patch.dict('sys.modules',{'pypdf':None}):
            with self.assertRaisesRegex(ValueError,'optional pypdf'):dq.extract(path)
        with self.assertRaises(ValueError):dq.extract(self.root/'file.html')

    def test_docx_table_extraction_order(self):
        path=self.root/'table.docx'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Experience</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>SQL</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>2020</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        result=dq.extract(path);self.assertEqual(result['tables'],1);self.assertEqual(result['text'],'Experience\nSQL\n2020')
        path.write_bytes(b'not a docx')
        with self.assertRaisesRegex(ValueError,'cannot be parsed'):dq.extract(path)

    def test_ats_detection_is_domain_bounded_and_has_generic_fallback(self):
        for ats,domains in aq.DOMAINS.items():
            for domain in domains:
                self.assertEqual(aq.detect('https://tenant.'+domain+'/careers'),ats)
                self.assertEqual(aq.detect('https://'+domain+'.attacker.invalid/form'),'generic')
        self.assertEqual(aq.detect('https://custom-employer.invalid/application'),'generic')

    def test_wrong_job_reuse_needs_exact_approved_exception(self):
        a,b=self.job(),self.job();doc=self.doc(a);self.approve(a,doc)
        with self.assertRaises(ValueError):self.op('document-attach-check',job_id=b,sha256=doc['sha256'])
        other=self.doc(b);self.approve(b,other)
        with self.assertRaisesRegex(ValueError,'exception'):self.op('document-attach-check',job_id=b,sha256=other['sha256'])
        self.op('document-exception',job_id=b,sha256=other['sha256'],candidate_instruction='Synthetic candidate explicitly permits these same bytes for job B',reason='Both synthetic postings have identical requirements')
        self.assertTrue(self.op('document-attach-check',job_id=b,sha256=other['sha256'])['allowed'])
        self.verify(b,other)
        with self.assertRaises(ValueError):self.op('document-attach-check',job_id=b,sha256=other['sha256'])

    def test_recruiter_blocker_and_stale_verification_approval(self):
        jid=self.job();doc=self.doc(jid);d=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2020–2024')
        d['critique']['findings']=[dict(severity='blocker',reason='Synthetic readability issue',evidence='Synthetic rendered line overlaps')]
        v=self.ws.mutate(d)
        with self.assertRaisesRegex(ValueError,'blockers'):self.op('document-approve',job_id=jid,sha256=doc['sha256'],verification_id=v['verification_id'],candidate_instruction='Approve')
        self.approve(jid,doc);aid=self.ready(jid)
        self.verify(jid,doc)
        self.assertEqual(preflight(self.ws,jid,aid)['status'],'failed')
        with self.assertRaises(ValueError):self.op('document-approve',job_id=jid,sha256=doc['sha256'],verification_id='old',candidate_instruction='Approve wrong review')

    def test_version_history_diffs_and_frozen_outcome_versions(self):
        jid=self.job();first=self.doc(jid);self.approve(jid,first)
        profile=self.ws.read()['profile'];profile['fixture_document']='SQL experience 2020–2024\nSQL';self.op('profile-save',profile=profile)
        second=self.doc(jid,profile['fixture_document'])
        v=self.verify(jid,second,expected_text=profile['fixture_document'],claims=[dict(kind='fact',text=profile['fixture_document'],sources=[dict(kind='profile',pointer='/fixture_document',quote=profile['fixture_document'])])])
        self.assertIn('+SQL',v['diff']);self.assertEqual(len(self.ws.read()['document_quality']['versions']),2)
        self.op('manual-submitted',job_id=jid,evidence='Synthetic candidate report')
        self.assertEqual(self.ws.read()['learning']['applications'][jid]['snapshot']['document_versions'][0]['sha256'],second['sha256'])

    def test_truthful_role_variants_in_analytics_and_wrong_family_blocked(self):
        jid=self.job();doc=self.doc(jid)
        vid=self.op('positioning-save',role_family='Analysis',label='SQL focus',focus=[dict(text='SQL',sources=[dict(kind='profile',pointer='/skills/0',quote='SQL')])],candidate_instruction='Synthetic variant approval')['variant_id']
        with self.assertRaises(ValueError):self.verify(jid,doc,variant_id=vid)
        self.op('learning-attribution',job_id=jid,fields={'role_family':'Analysis'},evidence={'role_family':'Synthetic posting'})
        self.approve(jid,doc,variant_id=vid);self.op('manual-submitted',job_id=jid,evidence='Synthetic sent report')
        factor=learning.analytics(self.ws.read())['factors']['positioning_variant'];self.assertEqual(factor[0]['value'],vid);self.assertEqual(factor[0]['n'],1)
        with self.assertRaises(ValueError):self.op('positioning-save',role_family='Analysis',label='Java',focus=[dict(text='Java',sources=[dict(kind='profile',pointer='/skills/0',quote='SQL')])],candidate_instruction='No unsupported skills')

    def test_field_memory_changed_wording_context_and_no_fill_inference(self):
        a,b=self.job(),self.job()
        def observe(jid,question,context='candidate contact'):
            return self.op('field-observe',job_id=jid,field='Contact preference',question=question,question_type='Contact-Preference',context=context,site='https://example.invalid/tenant',evidence='Synthetic exact label')
        first=observe(a,'Preferred contact method?');self.assertIsNone(first['approval'])
        self.op('field-approve',job_id=a,question_id=first['id'],value='Email',candidate_instruction='Synthetic candidate approves this exact wording',reuse=True)
        same=observe(b,'Preferred contact method?');self.assertEqual(same['approval']['value'],'Email')
        changed=observe(b,'May we text your phone?');self.assertTrue(changed['wording_changed']);self.assertIsNone(changed['approval'])
        self.assertEqual(changed['suggested_value'],'Email');self.assertEqual(self.ws.read()['backlog']['questions'][changed['id']]['status'],'open')
        different=observe(b,'Preferred contact method?','employer marketing consent');self.assertIsNone(different['suggested_value'])
        self.assertNotIn('checkpoint',self.ws.read()['jobs'][a])
        with self.assertRaises(ValueError):self.op('field-observe',job_id=a,field='Password',question='Password?',question_type='Password',context='account',site='https://example.invalid',evidence='secret')

    def test_observed_field_upload_values_and_errors_required(self):
        jid=self.job();self.op('select',job_id=jid);self.op('start',job_id=jid)
        c=dict(page_url='https://example.invalid/apply',step='Review',observation='Synthetic',answers=[dict(field='Skill',value='SQL',source='Profile')],unresolved=[],complete=True)
        with self.assertRaisesRegex(ValueError,'page confirms'):self.op('checkpoint',job_id=jid,checkpoint=c)
        c['answers']=observed(c['answers']);c['errors']=['Address rejected']
        with self.assertRaises(ValueError):self.op('checkpoint',job_id=jid,checkpoint=c)
        c['errors']=[];self.op('checkpoint',job_id=jid,checkpoint=c)

    def test_failure_types_counts_recovery_and_handoff(self):
        jid=self.job();d=dict(job_id=jid,site='https://tenant.myworkdayjobs.com/en/job',step='Address',failure_type='address_rejected',evidence='Synthetic visible rejection',next_action='Candidate correct address through visible fields',safe_method=True)
        self.assertFalse(self.op('failure-record',**d)['handoff'])
        self.assertTrue(self.op('failure-record',**d)['handoff']);self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Needs attention')
        report=aq.view(self.ws.read());self.assertEqual(report['common_failures'][0]['count'],2);self.assertEqual(report['failures'][0]['ats'],'workday')
        with self.assertRaises(ValueError):self.op('playbook-note',**d,recovery='Guess',verified=False)
        self.op('playbook-note',**d,recovery='Observed country selection restored correct region options',verified=True)
        for kind in ('form_unreadable','iframe_unavailable','captcha_mfa'):
            self.assertTrue(self.op('failure-record',**dict(d,job_id=self.job(),failure_type=kind))['handoff'])
        self.assertEqual(aq.detect('https://myworkdayjobs.com.attacker.invalid/job'),'generic')

    def test_pre_submit_every_mismatch_fails_without_consuming_grant(self):
        jid=self.job();aid=self.ready(jid)
        with self.assertRaises(ValueError):self.op('submit-begin',job_id=jid,authorization_id=aid)
        for change in [dict(company='Wrong'),dict(title='Wrong'),dict(job_url='https://example.invalid/other'),dict(page_url='https://wrong.invalid/form'),dict(answers=[{}]),dict(uploads=[{}]),dict(errors=['Rejected']),dict(required_complete=False),dict(submit_visible=False),dict(authorization_id='unknown')]:
            self.assertEqual(preflight(self.ws,jid,aid,**change)['status'],'failed')
            with self.assertRaises(ValueError):self.op('submit-begin',job_id=jid,authorization_id=aid)
        self.assertEqual(self.ws.read()['authorizations'][0]['used'],[])
        self.assertEqual(preflight(self.ws,jid,aid)['status'],'passed')
        with patch('application_quality.now',return_value=datetime.now(timezone.utc)+timedelta(minutes=6)):
            with self.assertRaises(ValueError):self.op('submit-begin',job_id=jid,authorization_id=aid)
        self.op('revoke',authorization_id=aid)
        with self.assertRaises(ValueError):self.op('submit-begin',job_id=jid,authorization_id=aid)

    def test_confirmation_screenshot_email_evidence_and_uncertain_no_retry(self):
        jid=self.job();aid=self.ready(jid);preflight(self.ws,jid,aid);self.op('submit-begin',job_id=jid,authorization_id=aid)
        self.op('uncertain',job_id=jid,evidence='Synthetic interrupted response')
        shot=self.root/'receipt.png';shot.write_bytes(b'synthetic screenshot fixture')
        ident=receipt(self.ws,jid,screenshot_path=str(shot),email=dict(message_id='synthetic-1',excerpt='Application received for this job',source_url='https://mail.google.com/mail/u/0/#synthetic',received_at=clock()))
        self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Submission uncertain')
        with self.assertRaises(ValueError):self.op('submit-begin',job_id=jid,authorization_id=aid)
        self.op('resolve',job_id=jid,result='submitted',evidence='Synthetic matched receipt',confirmation_id=ident)
        self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Submitted')

    def test_schema4_temporary_copy_backup_preserves_records_retry_idempotent(self):
        jid=self.job();doc=self.doc(jid);self.approve(jid,doc);aid=self.ready(jid)
        old=self.ws.read();old['schema_version']=4;old.pop('document_quality');old.pop('application_quality')
        source=self.root/'old.sqlite3'
        with closing(sqlite3.connect(source)) as db:db.execute('CREATE TABLE state(id INTEGER PRIMARY KEY,value TEXT)');db.execute('INSERT INTO state VALUES(1,?)',(json.dumps(old),));db.commit()
        target=self.root/'migration-copy';target.mkdir();shutil.copy2(source,target/'toolkit.sqlite3');ws=toolkit.Workspace(target)
        with patch('document_quality.upgrade',side_effect=ValueError('Synthetic upgrade failure')):
            with self.assertRaises(ValueError):ws.migrate()
        with closing(sqlite3.connect(ws.db_path)) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        result=ws.migrate()
        with closing(sqlite3.connect(result['backup'])) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        new=ws.read();self.assertEqual(new['schema_version'],5);self.assertEqual(new['authorizations'],old['authorizations']);self.assertEqual(new['jobs'],old['jobs']);self.assertEqual(new['learning'],old['learning'])
        self.assertTrue(new['document_quality']['versions'][dq.key(jid,doc['sha256'])]['legacy']);self.assertFalse(ws.migrate()['migrated'])

    def test_import_source_hash_and_profile_changes_invalidate_document(self):
        jid=self.job();doc=self.doc(jid);folder=self.ws.root/'imports';folder.mkdir()
        path=folder/'source.json';path.write_text(json.dumps({'documents':[{'text':'SQL experience 2020–2024'}]}))
        d=verification_payload(self.ws,jid,doc['sha256'],'SQL experience 2020–2024');d['claims'][0]['sources']=[dict(kind='import',path='imports/source.json',sha256=toolkit.file_digest(path),document_index=0,quote='SQL experience 2020–2024')]
        v=self.ws.mutate(d);self.op('document-approve',job_id=jid,sha256=doc['sha256'],verification_id=v['verification_id'],candidate_instruction='Synthetic approval')
        path.write_text('{}')
        with self.assertRaises(ValueError):self.op('document-attach-check',job_id=jid,sha256=doc['sha256'])
        self.approve(jid,doc);self.op('profile-save',profile={'fixture_document':'Changed facts'})
        with self.assertRaises(ValueError):self.op('document-attach-check',job_id=jid,sha256=doc['sha256'])

    def test_changed_field_can_be_reviewed_again_without_losing_history(self):
        jid=self.job()
        data=dict(job_id=jid,field='Contact',question='Preferred contact?',question_type='contact',context='candidate preference',site='https://example.invalid/tenant',evidence='Synthetic form')
        old=self.op('field-observe',**data)
        fresh=self.op('field-observe',**dict(data,question='Preferred contact method?'))
        self.op('field-approve',job_id=jid,question_id=fresh['id'],value='Email',candidate_instruction='Synthetic candidate confirms changed wording')
        self.assertTrue(self.ws.read()['application_quality']['fields'][old['id']]['superseded'])
        self.op('resume-inspect',job_id=jid,page_url='https://example.invalid/apply',result='safe',checked_at=clock(),evidence='Synthetic inspection')
        pending=self.ws.read()['jobs'][jid]['pending_answers']['Contact']
        aid=self.ready(jid,[dict(field='Contact',**pending)])
        self.assertEqual(preflight(self.ws,jid,aid)['status'],'passed')

if __name__=='__main__':unittest.main()
