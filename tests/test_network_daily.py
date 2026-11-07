import copy
import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from test_skill import toolkit
import networking
import daily
import learning
from job_search import rankings

def stamp(days=0):return (datetime.now(timezone.utc)+timedelta(days=days)).isoformat()

class NetworkDailyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.ws=toolkit.Workspace(self.root/'private');self.ws.initialize();self.counter=0
    def tearDown(self):self.temp.cleanup()
    def op(self,op,**data):return self.ws.mutate(dict(op=op,**data))
    def job(self,**extra):
        self.counter+=1
        return self.op('job-add',**dict(dict(title='Data Analyst',company='Fixture Employer',description='Synthetic role',location='Remote',source='Synthetic',url=f'https://careers.example.invalid/{self.counter}'),**extra))['job_id']
    def connections(self):
        path=self.root/'connections.csv';path.write_text('First Name,Last Name,URL,Company,Position,Schools,Former Employers\nSynthetic,Contact,https://www.linkedin.com/in/synthetic-fixture,Fixture Employer,Analyst,Example School,Old Employer\n',encoding='utf-8')
        result=self.op('network-import',path=str(path),user_supplied=True)
        return next(iter(self.ws.read()['networking']['connections'])),result,path
    def verified(self,cid):self.op('network-contact-verify',connection_id=cid,verified_at=stamp(),source_url='https://example.invalid/team',evidence='Synthetic team page links this exact professional and employer')
    def sequence(self):
        cid,_,_=self.connections();jid=self.job();self.verified(cid);s=self.op('network-sequence',connection_id=cid,job_id=jid)
        m=self.op('network-draft',sequence_id=s['id']);return cid,jid,s['id'],m['id']
    def authorize_message(self,mid):return self.op('network-authorize',message_id=mid,expires_at=stamp(1),candidate_instruction='Synthetic separate permission for this exact message')['authorization_id']
    def send(self,mid):
        aid=self.authorize_message(mid);self.op('network-send-begin',message_id=mid,authorization_id=aid);self.op('network-sent',message_id=mid,sent_at=stamp(),evidence='Synthetic observed sent message')
    def profile(self,**extra):return self.op('daily-profile-save',**dict(dict(name='Synthetic daily',role='Data Analyst',location='Remote',posted_within='any',capacity=5,rules={}),**extra))['profile_id']
    def daily_run(self,count=2,partial=False,profile=None):
        rid=self.op('daily-start',profile_id=profile or self.profile())['id'];sid=self.ws.read()['daily']['runs'][rid]['search_id'];self.op('portal-search-begin',search_id=sid)
        rows=[]
        for i in range(count):
            self.counter+=1
            rows.append(dict(title='Data Analyst '+str(self.counter),company='Fixture Employer',description='Synthetic SQL role',location='Remote',source_url='https://www.linkedin.com/jobs/view/'+str(self.counter),
                discovery={'published_at':stamp(-1)},application_route={'type':'external','url':'https://careers.example.invalid/role/'+str(self.counter),'employer_verified':True,'on_platform_available':False,'evidence':'Synthetic employer route and no on-platform application','checked_at':stamp()}))
        self.op('portal-search-results',search_id=sid,source='LinkedIn',jobs=rows)
        for source in ['LinkedIn','Indeed']:self.op('portal-source-finish',search_id=sid,source=source,status='blocked' if partial and source=='Indeed' else 'complete',note='Synthetic coverage evidence')
        self.op('portal-search-finish',search_id=sid);run=self.op('daily-build',run_id=rid)
        return rid,[x['job_id'] for x in run['items']]
    def fresh(self,jid):self.op('freshness-record',job_id=jid,open=True,route_valid=True,route_url='https://careers.example.invalid/apply',checked_at=stamp(),evidence='Synthetic current posting and route')

    def test_connection_file_import_dedup_private_evidence_and_no_scraping(self):
        cid,result,path=self.connections();c=self.ws.read()['networking']['connections'][cid]
        self.assertIsNone(c['last_verified_at']);self.assertTrue((self.ws.root/c['source']['path']).is_file())
        self.assertTrue(self.op('network-import',path=str(path),user_supplied=True)['duplicate'])
        with self.assertRaises(ValueError):self.op('network-import',path=str(path),user_supplied=False)
        with self.assertRaises(ValueError):self.op('network-import',path='https://linkedin.com/connections',user_supplied=True)
        self.assertEqual(result['count'],1)

    def test_zip_requires_selected_safe_connections_member(self):
        archive=self.root/'export.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('Connections.csv','Name,Company\nSynthetic Contact,Fixture Employer\n');z.writestr('../Connections.csv','bad')
        for member in [None,'../Connections.csv','Messages.csv']:
            with self.assertRaises(ValueError):self.op('network-import',path=str(archive),member=member,user_supplied=True)
        self.assertEqual(self.op('network-import',path=str(archive),member='Connections.csv',user_supplied=True)['count'],1)
        malformed=self.root/'bad.csv';malformed.write_text('Name,Company\n,Fixture\n')
        with self.assertRaises(ValueError):self.op('network-import',path=str(malformed),user_supplied=True)

    def test_matching_evidence_confidence_former_colleague_and_boost_toggle(self):
        cid,_,_=self.connections();jid=self.job()
        self.op('profile-save',profile={'education':[{'school':'Example School'}],'experience':[{'company':'Old Employer'}]})
        paths=networking.matches(self.ws.read(),self.ws.read()['jobs'][jid]);types={r['type'] for r in paths[0]['reasons']}
        self.assertEqual(types,{'direct_connection','shared_school','former_employer'});self.assertTrue(all(r['confidence']=='possible' for r in paths[0]['reasons']))
        self.op('network-relation',connection_id=cid,type='former_colleague',candidate_confirmation='Synthetic candidate says we worked together')
        self.assertIn('former_colleague',{r['type'] for r in networking.matches(self.ws.read(),self.ws.read()['jobs'][jid])[0]['reasons']})
        before=rankings(self.ws.read())[jid];self.assertEqual(before['warm_path']['boost'],5)
        self.op('network-config',config={'warm_boost':False});self.assertEqual(rankings(self.ws.read())[jid]['score'],before['score']-5)
        self.assertEqual(self.ws.read()['authorizations'],[])

    def test_sequence_timing_and_honest_draft(self):
        cid,jid,sid,mid=self.sequence();state=self.ws.read();self.assertEqual(state['networking']['sequences'][sid]['timing'],'before')
        self.assertIn('how the referral process works',state['networking']['messages'][mid]['body']);self.assertNotIn('worked together',state['networking']['messages'][mid]['body'])
        other=self.job();self.op('deadline-set',job_id=other,closing_at=stamp(1),evidence='Synthetic deadline')
        sequence=self.op('network-sequence',connection_id=cid,job_id=other);self.assertEqual(sequence['timing'],'after')
        draft=self.op('network-draft',sequence_id=sequence['id'])
        with self.assertRaises(ValueError):self.authorize_message(draft['id'])

    def test_outreach_exact_auth_dnc_and_ambiguous_send(self):
        cid,jid,sid,mid=self.sequence();other=self.op('network-draft',sequence_id=sid)['id'];aid=self.authorize_message(mid)
        with self.assertRaises(ValueError):self.op('network-send-begin',message_id=other,authorization_id=aid)
        self.op('network-dnc',connection_id=cid,enabled=True,reason='Synthetic opt-out')
        with self.assertRaises(ValueError):self.op('network-send-begin',message_id=mid,authorization_id=aid)
        self.op('network-dnc',connection_id=cid,enabled=False,reason='Synthetic candidate cleared restriction')
        self.op('network-send-begin',message_id=mid,authorization_id=aid);self.op('network-uncertain',message_id=mid,evidence='Synthetic send timed out')
        with self.assertRaises(ValueError):self.authorize_message(other)
        self.op('network-resolve',message_id=mid,result='not_sent',evidence='Synthetic UI confirms unsent draft')
        with self.assertRaises(ValueError):self.op('network-send-begin',message_id=mid,authorization_id=aid)
        self.assertTrue(self.ws.read()['networking']['grants'][aid]['used']);self.assertEqual(self.ws.read()['authorizations'],[])

    def test_cadence_reply_decline_and_network_analytics(self):
        cid,jid,sid,mid=self.sequence();self.send(mid)
        followup=self.op('network-draft',sequence_id=sid)['id']
        with self.assertRaises(ValueError):self.authorize_message(followup)
        self.op('network-state',sequence_id=sid,status='replied',occurred_at=stamp(),evidence='Synthetic response')
        with self.assertRaises(ValueError):self.op('network-draft',sequence_id=sid)
        self.op('network-state',sequence_id=sid,status='referred',occurred_at=stamp(),evidence='Synthetic confirmed referral')
        state=self.ws.read();summary=learning.analytics(state)['networking'];self.assertEqual(summary['sequence_counts']['referred'],1);self.assertEqual(summary['messages_sent'],1)
        self.assertEqual({t['kind'] for t in state['learning']['applications'][jid]['touches']},{'outreach','referral'})
        other=self.job();s=self.op('network-sequence',connection_id=cid,job_id=other)
        self.assertIn('interval',networking.stop_reason(self.ws.read(),s))

    def test_verify_recipient_and_invalid_configs(self):
        cid,_,_=self.connections();jid=self.job();s=self.op('network-sequence',connection_id=cid,job_id=jid);m=self.op('network-draft',sequence_id=s['id'])
        with self.assertRaises(ValueError):self.authorize_message(m['id'])
        for config in [{'followup_days':0},{'max_messages_30d':100},{'warm_boost':'true'}]:
            with self.assertRaises(ValueError):self.op('network-config',config=config)

    def test_primary_coverage_required_partial_kept_and_all_jobs_visible(self):
        profile=self.profile();r=self.op('daily-start',profile_id=profile)
        self.assertEqual(self.op('daily-start',profile_id=profile)['id'],r['id'])
        with self.assertRaises(ValueError):self.op('daily-build',run_id=r['id'])
        rid,ids=self.daily_run(count=7,partial=True,profile=self.profile(name='Second'))
        run=self.ws.read()['daily']['runs'][rid];self.assertEqual(run['coverage_status'],'partial');self.assertEqual(len(ids),5);self.assertEqual(len(run['audit']),2)
        self.assertEqual(len(self.ws.read()['jobs']),7)

    def test_capacity_claims_across_runs_and_materials_required(self):
        self.op('daily-config',capacity=1);rid,ids=self.daily_run(count=2);jid=ids[0]
        with self.assertRaises(ValueError):self.op('daily-prepare-begin',run_id=rid,job_id=jid,review_evidence='Reviewed synthetic flags')
        self.fresh(jid);self.op('daily-prepare-begin',run_id=rid,job_id=jid,review_evidence='Reviewed synthetic duplicate warnings')
        with self.assertRaises(ValueError):self.op('daily-prepared',run_id=rid,job_id=jid,status='prepared',evidence='No materials yet')
        self.op('daily-prepared',run_id=rid,job_id=jid,status='blocked',evidence='Synthetic missing candidate fact');self.op('daily-publish',run_id=rid)
        other,ids2=self.daily_run(count=1);self.assertEqual(ids2,[]);self.assertTrue(self.ws.read()['daily']['runs'][other]['audit'])

    def test_digest_approval_uses_exact_existing_authorization(self):
        rid,ids=self.daily_run(count=2);jid=ids[0]
        with self.assertRaises(ValueError):self.op('daily-decision',run_id=rid,job_id=jid,decision='approve',expires_at=stamp(1),candidate_instruction='Synthetic approval')
        self.fresh(jid);self.op('select',job_id=jid);self.op('start',job_id=jid)
        self.op('checkpoint',job_id=jid,checkpoint=dict(page_url='https://careers.example.invalid/apply',step='Review',observation='Synthetic complete form',answers=[],unresolved=[],complete=True));self.op('ready',job_id=jid)
        result=self.op('daily-decision',run_id=rid,job_id=jid,decision='approve',expires_at=stamp(1),candidate_instruction='Synthetic approval of this exact reviewed job')
        grant=self.ws.read()['authorizations'][-1];self.assertEqual(list(grant['fingerprints']),[jid]);self.assertEqual(result['authorization_id'],grant['id']);self.assertEqual(grant['used'],[])
        self.assertEqual(self.ws.read()['networking']['grants'],{})
        outside=self.job()
        with self.assertRaises(ValueError):self.op('daily-decision',run_id=rid,job_id=outside,decision='skip',candidate_instruction='Outside digest')

    def test_skip_snooze_and_publish_gate(self):
        rid,ids=self.daily_run(count=2)
        with self.assertRaises(ValueError):self.op('daily-publish',run_id=rid)
        self.op('daily-decision',run_id=rid,job_id=ids[0],decision='skip',candidate_instruction='Synthetic skip')
        with self.assertRaises(ValueError):self.op('daily-decision',run_id=rid,job_id=ids[1],decision='snooze',until=stamp(-1),candidate_instruction='Bad date')
        self.op('daily-decision',run_id=rid,job_id=ids[1],decision='snooze',until=stamp(2),candidate_instruction='Synthetic snooze');self.op('daily-publish',run_id=rid)
        self.assertEqual(self.ws.read()['daily']['runs'][rid]['status'],'published')

    def test_digest_telegram_opt_in_mocked_and_ambiguous_not_retried(self):
        rid,ids=self.daily_run(count=0);self.op('daily-publish',run_id=rid)
        with self.assertRaises(ValueError):self.op('daily-notify',run_id=rid)
        with patch('private_settings.send_telegram',side_effect=ValueError('Synthetic failure')) as send:
            result=self.op('daily-notify',run_id=rid,candidate_instruction='Synthetic explicit Telegram request');self.assertEqual(result['delivery'],'uncertain');send.assert_called_once()
            self.assertNotIn('Fixture Employer',send.call_args.args[1])
        with self.assertRaises(ValueError):self.op('daily-notify',run_id=rid,candidate_instruction='Do not replay')

    def test_verified_requisition_dedup_renamed_roles_and_agencies(self):
        ident=dict(employer='Fixture Employer',requisition_id='REQ-1',employer_domain='example.invalid',evidence='Synthetic exact employer requisition')
        jid=self.job(identity=ident);same=self.job(title='Business Intelligence Analyst',company='Agency Fixture',identity=ident)
        self.assertEqual(jid,same);self.assertEqual(len(self.ws.read()['jobs']),1);self.assertEqual(len(self.ws.read()['jobs'][jid]['duplicate_observations']),1)
        different=dict(ident,requisition_id='REQ-2');self.assertNotEqual(jid,self.job(identity=different))

    def test_quality_flags_and_repeat_warnings_never_hide(self):
        first=self.job();self.op('manual-submitted',job_id=first,evidence='Synthetic prior application')
        second=self.job(description='An evergreen talent pool requires upfront payment.',location='Elsewhere')
        self.op('job-quality',job_id=second,facts={'salary':{'maximum':20,'currency':'XTS','period':'hour'},'eligibility':{'sponsorship':False},'agency':True,'evidence':'Synthetic posting excerpt'},signals=[])
        rules={'minimum_salary':30,'currency':'XTS','period':'hour','locations':['Remote'],'eligibility':{'sponsorship':True}}
        flags=daily.warnings(self.ws.read(),self.ws.read()['jobs'][second],rules);kinds={f['kind'] for f in flags}
        self.assertTrue({'scam','evergreen','salary','location','eligibility','staffing_duplicate'}<=kinds)
        self.assertTrue(any('Repeat-application' in f['reason'] for f in flags));self.assertEqual(len(self.ws.read()['jobs']),2)
        for f in flags:self.assertTrue(f['evidence']);self.assertTrue(f['reason'])

    def test_schema3_migration_backup_learning_preserved_and_retry(self):
        jid=self.job();old=self.ws.read();old['schema_version']=3;old.pop('networking');old.pop('daily')
        old['jobs'][jid]['contacts']=[dict(name='Synthetic',relevance='Saved source',checked_at=stamp())]
        with closing(sqlite3.connect(self.ws.db_path)) as db:db.execute('UPDATE state SET value=?',(json.dumps(old),));db.commit()
        with patch('daily.upgrade',side_effect=ValueError('Synthetic migration failure')):
            with self.assertRaises(ValueError):self.ws.migrate()
        with closing(sqlite3.connect(self.ws.db_path)) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        result=self.ws.migrate()
        with closing(sqlite3.connect(result['backup'])) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        state=self.ws.read();self.assertEqual(state['learning'],old['learning']);self.assertEqual(state['authorizations'],old['authorizations']);self.assertIn('last_verified_at',state['jobs'][jid]['contacts'][0]);self.assertFalse(self.ws.migrate()['migrated'])

    def test_decline_adds_dnc_and_cadence_shows_evidence(self):
        cid,jid,sid,mid=self.sequence();self.send(mid)
        shown=networking.view(self.ws.read())['sequences'][0];self.assertIsNotNone(shown['next_followup_at']);self.assertTrue(shown['cadence_evidence'])
        self.op('network-state',sequence_id=sid,status='declined',occurred_at=stamp(),evidence='Synthetic person declined contact')
        self.assertTrue(self.ws.read()['networking']['dnc'])
        with self.assertRaises(ValueError):self.op('network-draft',sequence_id=sid)
        self.assertEqual(networking.matches(self.ws.read(),self.ws.read()['jobs'][jid]),[])

    def test_message_limit_applies_across_sequences(self):
        cid,jid,sid,mid=self.sequence();self.send(mid)
        self.op('network-config',config={'max_messages_30d':1})
        other=self.job();seq=self.op('network-sequence',connection_id=cid,job_id=other)
        self.assertIn('30-day',networking.stop_reason(self.ws.read(),seq))
        with self.assertRaises(ValueError):self.op('network-draft',sequence_id=seq['id'])

    def test_existing_contact_card_reverification(self):
        jid=self.job();contact=dict(name='Synthetic Recruiter',role='Recruiter',company='Fixture',relevance='Synthetic team evidence',source_url='https://example.invalid/team',relationship='likely')
        self.op('contact-add',job_id=jid,contact=contact);saved=self.ws.read()['jobs'][jid]['contacts'][0]
        self.assertTrue(saved['last_verified_at'])
        self.op('contact-verify',job_id=jid,contact_id=saved['id'],verified_at=stamp(),source_url='https://example.invalid/team2',evidence='Synthetic updated team page')
        updated=self.ws.read()['jobs'][jid]['contacts'][0];self.assertEqual(updated['verification_evidence'],'Synthetic updated team page');self.assertEqual(len(updated['verification_history']),1)
        with self.assertRaises(ValueError):self.op('contact-verify',job_id=jid,contact_id='unknown',verified_at=stamp(),source_url='https://example.invalid',evidence='Unknown')

    def test_prepared_digest_checks_actual_document_versions(self):
        rid,ids=self.daily_run(count=1);jid=ids[0];self.fresh(jid);self.op('daily-prepare-begin',run_id=rid,job_id=jid)
        self.op('evaluate',job_id=jid,evaluation=dict(strengths=[],gaps=[],unknowns=[],evidence=['Synthetic candidate facts'],recommendation='Review this fixture'))
        path=self.root/'resume.txt';path.write_text('Synthetic tailored resume')
        self.op('document-add',job_id=jid,kind='resume',path=str(path));doc=self.ws.read()['jobs'][jid]['documents'][0]
        (self.ws.root/doc['path']).write_text('Tampered synthetic content')
        with self.assertRaises(ValueError):self.op('daily-prepared',run_id=rid,job_id=jid,status='prepared',evidence='Must verify bytes')
        (self.ws.root/doc['path']).write_bytes(path.read_bytes())
        self.op('daily-prepared',run_id=rid,job_id=jid,status='prepared',evidence='Synthetic material visually reviewed');self.op('daily-publish',run_id=rid)
        self.assertEqual(self.ws.read()['daily']['runs'][rid]['status'],'published')

    def test_credentials_in_csv_headers_are_rejected(self):
        path=self.root/'bad-secrets.csv';path.write_text('Name,Company,Password\nSynthetic,Fixture,do-not-import\n')
        with self.assertRaises(ValueError):self.op('network-import',path=str(path),user_supplied=True)
        self.assertFalse(self.ws.read()['networking']['connections'])

if __name__=='__main__':unittest.main()
