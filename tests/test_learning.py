from quality_fixtures import preflight
import copy
import json
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from test_skill import toolkit
import learning
from job_search import rankings

NOW=datetime(2026,10,1,12,tzinfo=timezone.utc)
def stamp(days=0,minutes=0):return (NOW+timedelta(days=days,minutes=minutes)).isoformat()

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.ws=toolkit.Workspace(Path(self.temp.name)/'private');self.ws.initialize();self.count=0
        self.clock=patch('learning.now',return_value=NOW);self.clock.start()
        self.event_clock=patch.object(toolkit,'utc',return_value=stamp());self.event_clock.start()
        self.sid=self.op('search-start',role='Analyst',location='Remote')['search_id']

    def tearDown(self):self.clock.stop();self.event_clock.stop();self.temp.cleanup()
    def op(self,op,**data):return self.ws.mutate(dict(op=op,**data))
    def job(self,group='A',age=30,complete=True):
        self.count+=1
        self.op('search-results',search_id=self.sid,jobs=[dict(title='Synthetic Analyst',company='Fixture',url=f'https://example.invalid/{self.count}',description='Synthetic fixture',source=group,location='Remote',discovery={'published_at':stamp(-age-2)})],coverage={})
        jid=self.ws.read()['searches'][self.sid]['job_ids'][-1]
        fields=dict(role_family='Analysis',seniority='Mid',tailoring_approach=group,ats='Fixture ATS',referral_used=False,outreach_used=False)
        if complete:self.op('learning-attribution',job_id=jid,fields=fields,evidence={k:'Synthetic candidate/form evidence' for k in fields})
        self.op('evaluate',job_id=jid,evaluation=dict(score=80,strengths=[],gaps=[],unknowns=[],evidence=['Synthetic profile'],recommendation='Review',rationale='Synthetic comparison'))
        self.op('select',job_id=jid)
        self.op('freshness-record',job_id=jid,open=True,route_valid=True,route_url='https://example.invalid/apply',checked_at=datetime.now(timezone.utc).isoformat(),evidence='Synthetic current route')
        with patch('learning.now',return_value=NOW-timedelta(days=age,minutes=60)):self.op('start',job_id=jid)
        return jid
    def applied(self,group='A',age=30,complete=True):
        jid=self.job(group,age,complete);self.op('manual-submitted',job_id=jid,applied_at=stamp(-age),evidence='Synthetic candidate confirmation');return jid
    def response(self,jid,status='Interview',days=-25,ident=None):
        return self.op('learning-outcome',job_id=jid,status=status,occurred_at=stamp(days),evidence='Synthetic employer response',event_id=ident or status+jid)
    def cohorts(self,n=20):
        ids=[]
        for group in ['A','B']:
            for i in range(n):
                jid=self.applied(group);ids.append(jid)
                if group=='A' and i<10 or group=='B' and i<2:self.response(jid)
        return ids

    def test_attribution_snapshot_all_factors_and_no_draft_usage_inference(self):
        jid=self.job();self.op('outreach-draft',job_id=jid,recipient='Fixture',channel='email',text='Synthetic unsent draft')
        self.op('manual-submitted',job_id=jid,applied_at=stamp(-30),evidence='Candidate confirmed')
        snap=self.ws.read()['learning']['applications'][jid]['snapshot']
        self.assertFalse(snap['incomplete']);self.assertFalse(snap['outreach_used']);self.assertEqual(snap['posting_age_days'],2);self.assertEqual(snap['time_to_apply_minutes'],60)
        self.assertEqual(snap['document_versions'],[])
        for field in learning.FACTORS:self.assertIn(field,snap)
        with self.assertRaises(ValueError):self.op('learning-attribution',job_id=jid,fields={'seniority':'Senior'},evidence={'seniority':'Later change'})
        self.assertEqual(snap,self.ws.read()['learning']['applications'][jid]['snapshot'])

    def test_unknown_fields_and_unconfirmed_outcomes_excluded_from_denominator(self):
        jid=self.job(complete=False);self.response(jid,'Rejected')
        self.assertEqual(learning.analytics(self.ws.read())['overall']['n'],0)
        self.op('manual-submitted',job_id=jid,evidence='Date not known')
        a=learning.analytics(self.ws.read());self.assertEqual(a['overall']['n'],1);self.assertEqual(a['overall']['incomplete_n'],1);self.assertEqual(a['eligible_learning_n'],0)
        self.assertIsNone(a['overall']['median_reply_days']);self.assertEqual(a['factors']['seniority'][0]['value'],'Unknown')

    def test_funnel_counts_denominators_median_and_distinct_ever_events(self):
        a,b,c=self.applied(),self.applied(),self.applied()
        self.response(a,'Application received',-29);self.response(a,'Interview',-27);self.response(a,'Offer',-20)
        self.response(b,'Rejected',-23);self.response(c,'Application received',-29)
        result=learning.analytics(self.ws.read());m=result['overall']
        self.assertEqual((m['n'],m['responses'],m['interviews'],m['offers']),(3,2,1,1));self.assertAlmostEqual(m['response_rate'],2/3)
        self.assertEqual(m['median_reply_days'],5);self.assertEqual(m['reply_time_n'],2)
        self.assertIn('not yet reliable',m['reliability']);self.assertEqual(result['suggestions'],[])
        for factor in learning.FACTORS:self.assertEqual(sum(g['n'] for g in result['factors'][factor]),3)

    def test_approval_changes_only_future_ranking_and_guidance_undo_restores(self):
        self.cohorts();future=self.job('A');state=self.ws.read();base=rankings(state)[future]['score'];grants=copy.deepcopy(state['authorizations'])
        result=self.op('learning-propose');proposals=self.ws.read()['learning']['proposals'];self.assertEqual(len(result['proposal_ids']),2)
        self.assertEqual(rankings(self.ws.read())[future]['score'],base)
        for pid in result['proposal_ids']:
            with self.assertRaises(ValueError):self.op('learning-approve',proposal_id=pid,candidate_instruction='')
            self.op('learning-approve',proposal_id=pid,candidate_instruction='Synthetic candidate approved this exact proposal')
        self.assertEqual(rankings(self.ws.read())[future]['score'],min(100,base+5));self.assertEqual(len(learning.guidance(self.ws.read())),1)
        for pid in result['proposal_ids']:self.op('learning-undo',proposal_id=pid,candidate_instruction='Synthetic candidate undo')
        self.assertEqual(rankings(self.ws.read())[future]['score'],base);self.assertEqual(learning.guidance(self.ws.read()),[])
        self.assertEqual(self.ws.read()['authorizations'],grants)
        self.assertEqual(state['learning']['applications'],self.ws.read()['learning']['applications'])
        for p in proposals.values():self.assertIn('correlation',p['suggestion']['caution'])

    def test_minimum_samples_age_and_incomplete_exclusions(self):
        self.cohorts(19);self.assertEqual(self.op('learning-propose')['proposal_ids'],[])
        self.applied('A',age=1);self.applied('B',complete=False)
        self.assertEqual(learning.analytics(self.ws.read())['eligible_learning_n'],38);self.assertEqual(self.op('learning-propose')['proposal_ids'],[])
        self.applied('A');self.applied('B');self.assertTrue(self.op('learning-propose')['proposal_ids'])

    def test_stale_proposal_rejected_after_evidence_or_config_change(self):
        self.cohorts();pid=self.op('learning-propose')['proposal_ids'][0]
        self.op('learning-config',config={'minimum_sample':25},evidence='Candidate raised threshold')
        with self.assertRaises(ValueError):self.op('learning-approve',proposal_id=pid,candidate_instruction='Approve old proposal')
        self.assertEqual(self.ws.read()['learning']['proposals'][pid]['status'],'pending')
        self.assertEqual(learning.active(self.ws.read()),[])

    def test_hygiene_thresholds_acknowledgement_and_no_rejection(self):
        a=self.applied(age=20);b=self.applied(age=50);c=self.applied(age=60);self.response(c,'Interview',-2)
        rows={r['job_id']:r for r in learning.hygiene(self.ws.read())}
        self.assertEqual(rows[a]['label'],'No response yet');self.assertIn('not rejection',rows[b]['label']);self.assertNotIn(c,rows)
        self.response(b,'Application received',-1);self.assertNotIn(b,{r['job_id']:r for r in learning.hygiene(self.ws.read())})
        self.assertEqual(self.ws.read()['jobs'][a]['status'],'Submitted')
        self.op('learning-config',config={'stale_days':30,'silence_days':60},evidence='Candidate preference')
        self.assertEqual(learning.hygiene(self.ws.read()),[])

    def test_configuration_failures_roll_back(self):
        initial=self.ws.read()
        for config in [{'minimum_sample':2},{'stale_days':50,'silence_days':2},{'observation_days':1},{'stale_days':True},{'unknown':1}]:
            with self.assertRaises(ValueError):self.op('learning-config',config=config,evidence='Synthetic')
            self.assertEqual(self.ws.read(),initial)

    def test_rejection_reasons_explicit_dedup_and_recurrence(self):
        ids=[self.applied(),self.applied()]
        for jid in ids:
            self.response(jid,'Rejected')
            data=dict(job_id=jid,reason_id='r'+jid,category='skills',gap='SQL',stated_reason='We require deeper SQL experience',evidence='Synthetic employer email',occurred_at=stamp(-25))
            with self.assertRaises(ValueError):self.op('learning-rejection',**data)
            self.op('learning-rejection',**data,employer_stated=True)
            with self.assertRaises(ValueError):self.op('learning-rejection',**data,employer_stated=True)
        gap=learning.gaps(self.ws.read())[0];self.assertEqual(gap['n'],2);self.assertTrue(gap['recurring']);self.assertEqual(len(gap['evidence']),2)

    def test_outcome_dates_duplicates_and_no_uncertain_bypass(self):
        jid=self.applied();self.response(jid,ident='stable');self.response(jid,ident='stable');self.assertEqual(len(self.ws.read()['learning']['applications'][jid]['outcomes']),1)
        for occurred in [stamp(-40),stamp(3),'2026-01-01']:
            with self.assertRaises(ValueError):self.op('learning-outcome',job_id=jid,status='Offer',occurred_at=occurred,evidence='Invalid date',event_id='bad')
        other=self.job();self.op('checkpoint',job_id=other,checkpoint=dict(page_url='https://example.invalid/apply',step='Review',observation='Synthetic',answers=[],unresolved=[],complete=True));self.op('ready',job_id=other)
        aid=self.op('authorize',job_ids=[other],user_instruction='Synthetic permission',expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())['authorization_id']
        self.assertEqual(preflight(self.ws,other,aid)['status'],'passed')
        self.op('submit-begin',job_id=other,authorization_id=aid)
        self.assertFalse(self.ws.read()['learning']['applications'][other]['confirmed'])
        self.op('uncertain',job_id=other,evidence='Synthetic ambiguous browser result')
        with self.assertRaises(ValueError):self.response(other)
        self.assertEqual(learning.analytics(self.ws.read())['overall']['n'],1)

    def test_weekly_actions_events_dates_and_no_state_mutation(self):
        jid=self.applied(age=3);self.response(jid,days=-1);blocked=self.job();self.op('blocker-add',job_id=blocked,type='video_file',reason='Synthetic upload required',next_action='Provide requested file',evidence='Synthetic form')
        before=self.ws.read();review=learning.weekly(before)
        self.assertEqual(len(review['next_actions']),3);self.assertEqual(review['next_actions'][0]['job_id'],blocked)
        self.assertEqual(review['applied_job_ids'],[jid]);self.assertEqual(review['worked']['dated_results'][0]['status'],'Interview')
        self.assertEqual(before,self.ws.read())
        for action in review['next_actions']:self.assertTrue(action['reason']);self.assertTrue(action['evidence'])

    def test_gmail_pending_not_counted_applied_ack_then_reply(self):
        jid=self.applied();self.op('email-config',account='candidate@example.invalid',enabled=True,auto_apply=False)
        cid=self.op('email-check-start',account='candidate@example.invalid',job_ids=[jid],scope='Synthetic only')['check_id']
        email=dict(check_id=cid,message_id='abc123',job_id=jid,received_at=stamp(-2),sender='careers@example.invalid',subject='Fixture update',summary='Interview invitation',evidence='Synthetic invite',match_reason='Exact job',suggested_status='Interview',match_confidence='confirmed',classification_confidence='confirmed')
        result=self.op('email-record',**email);self.assertEqual(learning.analytics(self.ws.read())['overall']['interviews'],0)
        self.op('email-apply',email_id=result['email_id'],note='Synthetic review')
        self.assertEqual(learning.analytics(self.ws.read())['overall']['interviews'],1)
        self.op('email-record',**email);self.assertEqual(len(self.ws.read()['learning']['applications'][jid]['outcomes']),1)

    def test_schema2_copy_migration_preserves_state_backup_and_unknowns(self):
        jid=self.applied();self.op('outcome',job_id=jid,status='Rejected',evidence='Synthetic old outcome')
        old=self.ws.read();old['schema_version']=2;old.pop('learning')
        with closing(sqlite3.connect(self.ws.db_path)) as db:db.execute('UPDATE state SET value=?',(json.dumps(old),));db.commit()
        root=Path(self.temp.name)/'migration-copy';root.mkdir();shutil.copy2(self.ws.db_path,root/'toolkit.sqlite3');ws=toolkit.Workspace(root)
        result=ws.migrate()
        with closing(sqlite3.connect(result['backup'])) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        migrated=ws.read();self.assertEqual(migrated['jobs'],old['jobs']);self.assertEqual(migrated['authorizations'],old['authorizations'])
        snap=migrated['learning']['applications'][jid]['snapshot'];self.assertTrue(snap['backfilled']);self.assertTrue(snap['incomplete']);self.assertIsNone(snap['applied_at'])
        self.assertFalse(ws.migrate()['migrated']);self.assertEqual(len(list((root/'backups').glob('*.sqlite3'))),1)

    def test_migration_failure_rolls_back_and_is_retryable(self):
        old=self.ws.read();old['schema_version']=2;old.pop('learning')
        with closing(sqlite3.connect(self.ws.db_path)) as db:db.execute('UPDATE state SET value=?',(json.dumps(old),));db.commit()
        with patch('learning.upgrade',side_effect=ValueError('Synthetic migration failure')):
            with self.assertRaises(ValueError):self.ws.migrate()
        with closing(sqlite3.connect(self.ws.db_path)) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        self.assertTrue(self.ws.migrate()['migrated'])

    def test_dated_outreach_evidence_not_draft_or_permission(self):
        jid=self.applied();before=copy.deepcopy(self.ws.read()['learning']['applications'][jid]['snapshot'])
        data=dict(job_id=jid,kind='outreach',event_id='sent-1',occurred_at=stamp(-20),evidence='Synthetic candidate reported previously sent message')
        with self.assertRaises(ValueError):self.op('learning-touch',**data)
        self.op('learning-touch',**data,observed=True)
        state=self.ws.read();self.assertEqual(before,state['learning']['applications'][jid]['snapshot']);self.assertEqual(state['authorizations'],[])
        self.assertEqual(learning.analytics(state)['factors']['outreach_used'][0]['value'],'Yes')
        self.assertEqual(learning.analytics(state,NOW-timedelta(days=25))['factors']['outreach_used'][0]['value'],'No')

    def test_conflicting_source_id_and_undated_outcome(self):
        jid=self.applied();self.response(jid,ident='source-1')
        with self.assertRaises(ValueError):self.response(jid,'Offer',ident='source-1')
        self.op('outcome',job_id=jid,status='Rejected',evidence='Synthetic user report with unknown date')
        self.assertIsNone(self.ws.read()['learning']['applications'][jid]['outcomes'][-1]['occurred_at'])
        self.assertEqual(learning.analytics(self.ws.read())['eligible_learning_n'],0)

    def test_document_versions_and_fit_are_frozen_at_application(self):
        jid=self.job();path=Path(self.temp.name)/'resume.txt';path.write_text('Synthetic resume version one')
        self.op('document-add',job_id=jid,kind='resume',path=str(path))
        self.op('manual-submitted',job_id=jid,applied_at=stamp(-30),evidence='Synthetic candidate statement')
        before=copy.deepcopy(self.ws.read()['learning']['applications'][jid]['snapshot'])
        self.op('evaluate',job_id=jid,evaluation=dict(score=20,strengths=[],gaps=[],unknowns=[],evidence=['Later synthetic review'],recommendation='Review',rationale='New assessment'))
        self.assertEqual(self.ws.read()['learning']['applications'][jid]['snapshot'],before)
        group=learning.analytics(self.ws.read())['factors']['document_versions'][0]
        self.assertIn(before['document_versions'][0]['sha256'],group['value']);self.assertEqual(before['fit_score'],80)

    def test_undated_outcome_never_fabricates_response_time(self):
        jid=self.applied();self.op('outcome',job_id=jid,status='Interview',evidence='Date unknown')
        stats=learning.analytics(self.ws.read())['overall'];self.assertEqual(stats['responses'],1);self.assertIsNone(stats['median_reply_days']);self.assertEqual(stats['reply_time_unknown_n'],1)

if __name__=='__main__':unittest.main()
