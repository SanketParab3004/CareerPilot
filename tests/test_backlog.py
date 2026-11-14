from quality_fixtures import observed, preflight
import copy
from contextlib import closing
import json
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from test_skill import toolkit
import backlog


def clock(hours=0):
    return (datetime.now(timezone.utc)+timedelta(hours=hours)).isoformat()


class BacklogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ws = toolkit.Workspace(Path(self.temp.name)/'private')
        self.ws.initialize()
        self.count = 0

    def tearDown(self):
        self.temp.cleanup()

    def op(self, op, **args):
        return self.ws.mutate(dict(op=op, **args))

    def job(self, fresh=True):
        self.count += 1
        jid = self.op('job-add', title='Synthetic analyst', company='Fixture', description='Fixture', source='Test', url=f'https://example.invalid/jobs/{self.count}')['job_id']
        if fresh: self.fresh(jid)
        self.op('select',job_id=jid)
        return jid

    def fresh(self,jid,**changes):
        self.op('freshness-record', **dict(dict(job_id=jid,open=True,route_valid=True,route_url='https://example.invalid/apply',checked_at=clock(),evidence='Synthetic open posting and employer route'),**changes))

    def block(self,jid,**changes):
        return self.op('blocker-add', **dict(dict(job_id=jid,type='login_account',site='https://example.invalid/tenant-a',reason='Synthetic login needed',next_action='Log into tenant A',evidence='Synthetic login screen',estimated_minutes=5),**changes))['blocker_id']

    def inspect(self,jid,**changes):
        return self.op('resume-inspect',**dict(dict(job_id=jid,page_url='https://example.invalid/apply',checked_at=clock(),result='safe',evidence='Synthetic live form matches role and saved answers; no submit occurred'),**changes))

    def checkpoint(self,jid,**changes):
        if 'answers' in changes: changes['answers']=observed(changes['answers'])
        self.op('checkpoint',job_id=jid,checkpoint=dict(dict(page_url='https://example.invalid/apply',step='Review',answers=[],unresolved=[],complete=True,observation='Synthetic final review'),**changes))

    def question(self,jid,context='candidate.preference'):
        return self.op('question-add',job_id=jid,field='Preference',question='Which work arrangement do you prefer?',context=context,evidence='Synthetic required form field')['question_id']

    def legacy_copy(self):
        jid=self.job();self.block(jid)
        state=self.ws.read();state['schema_version']=1;state.pop('backlog')
        state['jobs'][jid].update(blocker='Original free text <data>',next_action='Ask user',checkpoint=dict(answers=[],unresolved=['Unknown legacy question'],observation='Saved'))
        with closing(sqlite3.connect(self.ws.db_path)) as db:
            db.execute('UPDATE state SET value=?',(json.dumps(state),));db.commit()
        target=Path(self.temp.name)/'copy';target.mkdir();shutil.copy2(self.ws.db_path,target/'toolkit.sqlite3')
        return toolkit.Workspace(target),state,jid

    def test_migration_backup_original_preserved_and_idempotent(self):
        ws,old,jid=self.legacy_copy();result=ws.migrate()
        with closing(sqlite3.connect(result['backup'])) as db: self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        self.assertFalse(ws.migrate()['migrated'])
        self.assertEqual(len(list((ws.root/'backups').glob('*.sqlite3'))),1)
        state=ws.read();item=state['backlog']['blockers']['legacy-'+jid]
        self.assertEqual(item['original_text'],'Original free text <data>');self.assertEqual(item['type'],'needs_review')
        self.assertEqual(len(state['backlog']['questions']),1);self.assertTrue(state['jobs'][jid]['resume_required'])
        self.assertEqual(state['jobs'][jid]['checkpoint_history'][0],old['jobs'][jid]['checkpoint'])
        self.assertTrue(backlog.queue(state))

    def test_failed_migration_leaves_old_state_and_backup(self):
        ws,old,_=self.legacy_copy()
        with patch('backlog.upgrade',side_effect=ValueError('synthetic failure')):
            with self.assertRaises(ValueError): ws.migrate()
        with closing(sqlite3.connect(ws.db_path)) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)
        self.assertEqual(len(list((ws.root/'backups').glob('*.sqlite3'))),1)
        self.assertTrue(ws.migrate()['migrated'])

    def test_backup_failure_never_migrates(self):
        ws,old,_=self.legacy_copy();(ws.root/'backups').write_text('not a folder')
        with self.assertRaises(OSError):ws.migrate()
        with closing(sqlite3.connect(ws.db_path)) as db:self.assertEqual(json.loads(db.execute('SELECT value FROM state').fetchone()[0]),old)

    def test_future_schema_rejected_without_write(self):
        with closing(sqlite3.connect(self.ws.db_path)) as db:
            state=toolkit.fresh();state['schema_version']=999;db.execute('UPDATE state SET value=?',(json.dumps(state),));db.commit()
        original=self.ws.db_path.read_bytes()
        with self.assertRaises(ValueError):self.ws.read()
        self.assertEqual(self.ws.db_path.read_bytes(),original)

    def test_queue_priority_fields_and_type_tenant_groups(self):
        a,b=self.job(),self.job();self.block(a);self.block(b,site='https://example.invalid/tenant-b',deadline=clock(2))
        rows=backlog.queue(self.ws.read());self.assertEqual(rows[0]['job_id'],b);self.assertEqual(rows[0]['urgency'],'due_soon')
        self.assertEqual(len({r['site'] for r in rows}),2)
        for row in rows:
            for key in ['reason','evidence','next_action','owner','deadline','estimated_minutes','priority_reason']:self.assertIn(key,row)

    def test_invalid_blocker_rolls_back(self):
        jid=self.job();old=self.ws.read()
        for changes in [dict(type='invented'),dict(owner='nobody'),dict(site='https://user:secret@example.invalid'),dict(estimated_minutes=-1),dict(deadline='tomorrow')]:
            with self.assertRaises(ValueError):self.block(jid,**changes)
            self.assertEqual(old,self.ws.read())

    def test_login_session_exact_tenant_and_live_gate(self):
        a,b,c=self.job(),self.job(),self.job();self.block(a);self.block(b);self.block(c,site='https://example.invalid/tenant-b')
        before=copy.deepcopy(self.ws.read()['authorizations'])
        session=self.op('login-session-start',site='https://example.invalid/tenant-a');self.assertEqual(set(session['job_ids']),{a,b})
        self.op('login-session-complete',session_id=session['id'],evidence='Candidate completed login')
        with self.assertRaises(ValueError):self.op('start',job_id=a)
        self.inspect(a);self.op('start',job_id=a)
        self.assertEqual(self.ws.read()['jobs'][c]['status'],'Needs attention');self.assertEqual(before,self.ws.read()['authorizations'])
        with self.assertRaises(ValueError):self.op('login-session-complete',session_id=session['id'],evidence='again')

    def test_login_session_does_not_clear_other_blocker(self):
        jid=self.job();self.block(jid);self.block(jid,type='video_file')
        s=self.op('login-session-start',site='https://example.invalid/tenant-a');self.op('login-session-complete',session_id=s['id'],evidence='Candidate finished login')
        self.inspect(jid)
        with self.assertRaises(ValueError):self.op('start',job_id=jid)

    def test_answers_batch_and_exact_context_and_future_reuse(self):
        a,b,c=self.job(),self.job(),self.job();qa=self.question(a);qb=self.question(b);qc=self.question(c,'different jurisdiction')
        result=self.op('answer-save',question_id=qa,value='Remote',evidence='Synthetic candidate statement',reuse=True)
        self.assertEqual(set(result['question_ids']),{qa,qb});self.assertEqual(self.ws.read()['backlog']['questions'][qc]['status'],'open')
        with self.assertRaises(ValueError):self.op('start',job_id=a)
        self.inspect(a);self.op('start',job_id=a)
        self.assertEqual(self.ws.read()['jobs'][b]['pending_answers']['Preference']['value'],'Remote')
        d=self.job();qd=self.question(d);self.assertEqual(self.ws.read()['backlog']['questions'][qd]['status'],'answered')

    def test_unknown_answer_and_duplicate_answer_rejected(self):
        jid=self.job();q=self.question(jid)
        with self.assertRaises(ValueError):self.op('answer-save',question_id=q,value='',evidence='Unknown')
        self.assertEqual(self.ws.read()['backlog']['questions'][q]['status'],'open')
        self.op('answer-save',question_id=q,value='Remote',evidence='Candidate statement')
        with self.assertRaises(ValueError):self.op('answer-save',question_id=q,value='Other',evidence='Duplicate')

    def test_checkpoint_history_questions_and_restart(self):
        jid=self.job();self.op('start',job_id=jid);self.checkpoint(jid);self.checkpoint(jid,unresolved=['Required answer'],complete=False)
        self.ws=toolkit.Workspace(self.ws.root)
        self.assertEqual(len(self.ws.read()['jobs'][jid]['checkpoint_history']),2)
        self.assertEqual(len(self.ws.read()['backlog']['questions']),1)
        self.op('interrupt',job_id=jid,evidence='Synthetic browser closed')
        with self.assertRaises(ValueError):self.checkpoint(jid)
        self.inspect(jid,result='uncertain')
        self.assertTrue(self.ws.read()['jobs'][jid]['resume_required'])

    def test_credential_word_in_unresolved_note_can_be_answered(self):
        note='Sign-in required (email, password, consent to terms)'
        jid=self.job();self.op('start',job_id=jid);self.checkpoint(jid,unresolved=[note],complete=False)
        q=next(q for q in self.ws.read()['backlog']['questions'].values() if q['job_id']==jid)
        self.assertEqual(q['field'],'Sign-in required (email, [credential], consent to terms)')
        self.op('answer-save',question_id=q['id'],value='Candidate signed in',evidence='Synthetic candidate statement')
        self.inspect(jid)
        source=self.ws.read()['jobs'][jid]['pending_answers'][q['field']]['source']
        with self.assertRaises(ValueError):self.checkpoint(jid,answers=[dict(field='Password',value='Candidate signed in',source=source)])
        self.checkpoint(jid,answers=[dict(field=q['field'],value='Candidate signed in',source=source)])
        self.assertEqual(self.op('ready',job_id=jid)['status'],'Ready for review')

    def test_unmasked_pending_answer_from_older_state_can_be_confirmed(self):
        note='Workday sign-in (password) needed'
        jid=self.job();self.op('start',job_id=jid)
        state=self.ws.read();state['jobs'][jid]['pending_answers']={note:dict(value='Signed in',source='candidate answer old')}
        with closing(sqlite3.connect(self.ws.db_path)) as db:
            db.execute('UPDATE state SET value=?',(json.dumps(state),));db.commit()
        self.checkpoint(jid,answers=[dict(field='Workday sign-in ([credential]) needed',value='Signed in',source='candidate answer old')])
        self.assertEqual(self.ws.read()['jobs'][jid]['pending_answers'],{})

    def test_stale_and_wrong_destination_inspections_rejected(self):
        jid=self.job();self.op('interrupt',job_id=jid,evidence='Synthetic crash')
        for changes in [dict(checked_at=clock(-1)),dict(page_url='https://other.invalid/apply'),dict(result='guess')]:
            with self.assertRaises(ValueError):self.inspect(jid,**changes)
        self.assertTrue(self.ws.read()['jobs'][jid]['resume_required'])
        self.inspect(jid);self.op('start',job_id=jid)

    def test_uncertain_submission_cannot_resume_or_reuse_grant(self):
        jid=self.job();self.op('start',job_id=jid);self.checkpoint(jid);self.op('ready',job_id=jid)
        grant=self.op('authorize',job_ids=[jid],user_instruction='Synthetic permission',expires_at=clock(1))['authorization_id']
        self.assertEqual(preflight(self.ws,jid,grant)['status'],'passed')
        self.op('submit-begin',job_id=jid,authorization_id=grant);self.op('interrupt',job_id=jid,evidence='Synthetic crash after click')
        self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Submission uncertain')
        for op,args in [('start',{}),('submit-begin',{'authorization_id':grant}),('resume-inspect',dict(page_url='https://example.invalid/apply',result='safe',checked_at=clock(),evidence='Guess')),('blocker-add',dict(type='login_account',reason='login',next_action='login'))]:
            with self.assertRaises(ValueError):self.op(op,job_id=jid,**args)
        self.assertEqual(self.ws.read()['authorizations'][0]['used'],[jid])

    def test_freshness_and_deadline_gate(self):
        jid=self.job(False)
        with self.assertRaises(ValueError):self.op('start',job_id=jid)
        self.fresh(jid,open=False)
        with self.assertRaises(ValueError):self.op('start',job_id=jid)
        with self.assertRaises(ValueError):self.fresh(jid,checked_at=clock(-25))
        self.fresh(jid);self.op('deadline-set',job_id=jid,closing_at=clock(-1),evidence='Synthetic closing date')
        with self.assertRaises(ValueError):self.op('start',job_id=jid)
        self.assertEqual(backlog.queue(self.ws.read())[0]['urgency'],'overdue')
        self.op('deadline-set',job_id=jid,closing_at=None,evidence='Employer removed closing date');self.op('start',job_id=jid)

    def test_handoff_draft_does_not_send_or_authorize_outreach(self):
        jid=self.job();h=self.op('handoff-draft',job_id=jid,recipient='careers@example.invalid',subject='Fixture application',body='Synthetic draft',evidence='Fixture employer requires personal email')['handoff_id']
        self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Selected');self.assertEqual(self.ws.read()['authorizations'],[])
        with self.assertRaises(ValueError):self.op('handoff-sent',job_id=jid,handoff_id=h,evidence='No confirmation',sent_at=clock())
        self.op('handoff-sent',job_id=jid,handoff_id=h,evidence='Candidate reported sent',sent_at=clock(),candidate_confirmed=True)
        self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Submitted');self.assertEqual(backlog.queue(self.ws.read()),[])
        with self.assertRaises(ValueError):self.op('handoff-sent',job_id=jid,handoff_id=h,evidence='Again',sent_at=clock(),candidate_confirmed=True)

    def test_sensitive_fields_and_pending_answer_checkpoint_guard(self):
        jid=self.job()
        with self.assertRaises(ValueError):self.op('question-add',job_id=jid,field='password',question='Your password?',context='account',evidence='Form')
        q=self.question(jid);self.op('answer-save',question_id=q,value='Remote',evidence='Candidate statement')
        self.inspect(jid);self.op('start',job_id=jid)
        with self.assertRaises(ValueError):self.checkpoint(jid)
        pending=self.ws.read()['jobs'][jid]['pending_answers']['Preference']
        self.checkpoint(jid,answers=[dict(field='Preference',**pending)])
        self.op('ready',job_id=jid)

    def test_frozen_login_session_and_authorization_unchanged(self):
        a=self.job();self.op('start',job_id=a);self.checkpoint(a);self.op('ready',job_id=a)
        self.op('authorize',job_ids=[a],user_instruction='Synthetic approval for A only',expires_at=clock(1))
        before=copy.deepcopy(self.ws.read()['authorizations']);self.block(a)
        session=self.op('login-session-start',site='https://example.invalid/tenant-a')
        b=self.job();self.block(b)
        self.assertEqual(session,self.op('login-session-start',site='https://example.invalid/tenant-a'))
        self.op('login-session-complete',session_id=session['id'],evidence='Candidate logged in');self.inspect(a)
        self.assertEqual(before,self.ws.read()['authorizations']);self.assertEqual(self.ws.read()['jobs'][b]['status'],'Needs attention')

    def test_deadline_at_import_requires_source_and_timezone(self):
        args=dict(title='Synthetic',company='Fixture',description='Test',source='Test',url='https://example.invalid/deadline',closing_at=clock(24))
        with self.assertRaises(ValueError):self.op('job-add',**args)
        jid=self.op('job-add',**args,closing_evidence='Synthetic employer closing date')['job_id']
        self.assertEqual(self.ws.read()['jobs'][jid]['closing_at'],args['closing_at'])
        with self.assertRaises(ValueError):self.op('deadline-set',job_id=jid,closing_at='2030-01-01',evidence='Date without zone')

    def test_answer_reuse_skips_finished_jobs(self):
        a,b=self.job(),self.job();qa=self.question(a);qb=self.question(b)
        self.op('outcome',job_id=b,status='Withdrawn',evidence='Synthetic candidate withdrawal')
        result=self.op('answer-save',question_id=qa,value='Remote',evidence='Synthetic candidate answer',reuse=True)
        self.assertEqual(result['question_ids'],[qa]);self.assertEqual(self.ws.read()['backlog']['questions'][qb]['status'],'open')

if __name__=='__main__':unittest.main()
