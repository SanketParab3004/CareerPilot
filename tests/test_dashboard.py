import hashlib
from datetime import datetime, timezone
import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from test_skill import ROOT, load, toolkit

sys.path.insert(0, str(ROOT / 'skills' / 'careerpilot' / 'scripts'))
dashboard = load('dashboard', ROOT / 'skills' / 'careerpilot' / 'scripts' / 'dashboard.py')


class DashboardTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'work'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.ws = toolkit.Workspace(Path(self.temp.name) / 'private')
        self.ws.initialize()
        self.server = dashboard.DashboardServer(self.ws.root, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.prefix = '/' + self.server.token + '/'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, route, method='GET', headers=None, prefix=True, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request(method, (self.prefix if prefix else '') + route, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_live_state_reads_same_workspace_without_writes(self):
        initial = hashlib.sha256(self.ws.db_path.read_bytes()).hexdigest()
        status, headers, raw = self.get('api/state')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['state']['profile'], {})
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(hashlib.sha256(self.ws.db_path.read_bytes()).hexdigest(), initial)
        self.ws.mutate({'op':'profile-save', 'profile':{'name':'Synthetic Candidate'}})
        self.assertEqual(json.loads(self.get('api/state')[2])['state']['profile']['name'], 'Synthetic Candidate')

    def test_action_queue_and_answer_controls(self):
        jid=self.ws.mutate(dict(op='job-add',title='Synthetic',company='Fixture',description='Test',source='Test',url='https://example.invalid/job'))['job_id']
        q=self.ws.mutate(dict(op='question-add',job_id=jid,question='Preferred arrangement?',context='candidate.preference',field='arrangement',evidence='Synthetic form'))['question_id']
        payload=json.loads(self.get('api/state')[2]);self.assertTrue(any(x['id']==q for x in payload['action_queue']))
        data=json.dumps(dict(question_id=q,value='Remote',evidence='Synthetic candidate answer',reuse=True))
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'answer-save','Origin':self.server.origin}
        self.assertEqual(self.get('api/answer-save','POST',body=data)[0],403)
        self.assertEqual(self.get('api/answer-save','POST',headers=headers,body=data)[0],202)
        self.assertEqual(self.ws.read()['backlog']['questions'][q]['status'],'answered')
        self.assertEqual(self.get('api/answer-save','POST',headers=headers,body=data)[0],400)
        for action in ['login-session-start','login-session-complete','handoff-sent']:
            self.assertEqual(self.get('api/'+action,'POST',body='{}')[0],403)
        for action in ['resume-inspect','freshness-record','submit-begin','handoff-send']:
            self.assertEqual(self.get('api/'+action,'POST',headers=headers,body='{}')[0],405)
        self.assertIn(b'Action queue',self.get('')[2])

    def test_token_host_and_cross_site_protection(self):
        self.assertEqual(self.get('/api/state', prefix=False)[0], 404)
        self.assertEqual(self.get('api/state', headers={'Host':'external.example'})[0], 403)
        self.assertEqual(self.get('api/state', headers={'Origin':'https://external.example'})[0], 403)
        self.assertEqual(self.get('api/state', headers={'Sec-Fetch-Site':'cross-site'})[0], 403)
        self.assertEqual(self.get('api/state', headers={'Origin':self.server.origin})[0], 200)

    def test_learning_views_preferences_and_approval_boundary(self):
        payload=json.loads(self.get('api/state')[2]);self.assertEqual(payload['analytics']['overall']['n'],0)
        self.assertEqual(len(payload['weekly']['next_actions']),3)
        for label in [b'Funnel analytics',b'Weekly review']:self.assertIn(label,self.get('')[2])
        for action in ['learning-config','learning-propose','learning-approve','learning-undo']:
            self.assertEqual(self.get('api/'+action,'POST',body='{}')[0],403)
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'learning-config','Origin':self.server.origin}
        self.assertEqual(self.get('api/learning-config','POST',headers=headers,body=json.dumps({'config':{'stale_days':21},'evidence':'Synthetic candidate preference'}))[0],202)
        self.assertEqual(self.ws.read()['learning']['config']['stale_days'],21)
        self.assertEqual(self.get('api/learning-config','POST',headers=headers,body=json.dumps({'config':{'minimum_sample':1},'evidence':'Synthetic'}))[0],400)
        headers['X-CareerPilot-Request']='learning-propose'
        self.assertEqual(json.loads(self.get('api/learning-propose','POST',headers=headers,body='{}')[2])['proposal_ids'],[])
        for route in ['learning-outcome','learning-attribution','learning-touch','email-send']:
            self.assertEqual(self.get('api/'+route,'POST',headers=headers,body='{}')[0],405)

    def test_network_daily_views_and_no_message_send_api(self):
        payload=json.loads(self.get('api/state')[2]);self.assertEqual(payload['networking']['connections'],[]);self.assertEqual(payload['daily']['config']['capacity'],5)
        for label in [b'Referrals',b'Daily digest']:self.assertIn(label,self.get('')[2])
        for action in ['network-config','network-dnc','daily-config','daily-start','daily-decision']:
            self.assertEqual(self.get('api/'+action,'POST',body='{}')[0],403)
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'network-config','Origin':self.server.origin}
        self.assertEqual(self.get('api/network-config','POST',headers=headers,body=json.dumps({'config':{'warm_boost':False}}))[0],202)
        self.assertFalse(self.ws.read()['networking']['config']['warm_boost'])
        headers['X-CareerPilot-Request']='daily-profile-save'
        status,_,raw=self.get('api/daily-profile-save','POST',headers=headers,body=json.dumps({'name':'Synthetic','role':'Analyst','location':'Remote'}));self.assertEqual(status,202)
        profile=json.loads(raw)['profile_id'];headers['X-CareerPilot-Request']='daily-start'
        status,_,raw=self.get('api/daily-start','POST',headers=headers,body=json.dumps({'profile_id':profile}));self.assertEqual(status,202);self.assertEqual(json.loads(raw)['status'],'awaiting_agent')
        for action in ['network-import','network-authorize','network-send-begin','network-sent','daily-notify','submit-begin']:
            self.assertEqual(self.get('api/'+action,'POST',headers=headers,body='{}')[0],405)

    def test_static_assets_are_allowlisted_and_have_csp(self):
        for route in ['', 'app.js', 'style.css']:
            status, headers, body = self.get(route)
            self.assertEqual(status, 200)
            self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
            self.assertNotIn("'unsafe-inline'", headers['Content-Security-Policy'])
            self.assertTrue(body)
        for route in ['../toolkit.sqlite3','%2e%2e/toolkit.sqlite3','api/../toolkit.sqlite3','toolkit.sqlite3']:
            self.assertEqual(self.get(route)[0], 404)

    def test_mutations_are_not_available(self):
        for method in ['POST','PUT','PATCH','DELETE']:
            self.assertEqual(self.get('api/state', method)[0], 405)
        self.assertEqual(self.ws.read()['profile_revision'], 0)

    def test_registered_document_download_and_tamper_detection(self):
        jid = self.ws.mutate({'op':'job-add','title':'Synthetic Role','company':'Fixture','description':'Test','source':'Fixture','url':'https://example.invalid/job'})['job_id']
        self.ws.mutate(dict(op='freshness-record',job_id=jid,open=True,route_valid=True,route_url='https://example.invalid/apply',checked_at=datetime.now(timezone.utc).isoformat(),evidence='Synthetic fixture'))
        source = Path(self.temp.name) / 'resume.html'
        source.write_text('<script>test()</script>', encoding='utf-8')
        self.ws.mutate({'op':'document-add','job_id':jid,'kind':'resume','path':str(source)})
        doc = self.ws.read()['jobs'][jid]['documents'][0]
        route = f'api/document?job={jid}&sha={doc["sha256"]}'
        status, headers, body = self.get(route)
        self.assertEqual(status, 200)
        self.assertEqual(body, source.read_bytes())
        self.assertEqual(headers['Content-Type'], 'application/octet-stream')
        self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))
        (self.ws.root/doc['path']).write_text('tampered',encoding='utf-8')
        self.assertEqual(self.get(route)[0],409)
        self.assertEqual(self.get('api/document?job=unknown&sha=../../toolkit.sqlite3')[0],404)

    def test_export_and_unavailable_database(self):
        status, headers, raw = self.get('api/export')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), self.ws.read())
        self.assertIn('attachment;',headers['Content-Disposition'])
        self.ws.db_path.rename(self.ws.root/'moved.sqlite3')
        self.assertEqual(self.get('api/state')[0], 503)
        self.assertFalse(self.ws.db_path.exists())

    def test_missing_workspace_is_not_created(self):
        with self.assertRaises(sqlite3.OperationalError):
            dashboard.DashboardServer(Path(self.temp.name)/'missing',0)
        self.assertFalse((Path(self.temp.name)/'missing').exists())

    def test_search_post_requires_same_origin_and_starts_real_workflow(self):
        from test_search import FakeClient
        self.server.search.client=FakeClient()
        payload=json.dumps({'role':'Data Analyst','location':'New York','posted_within':'7'})
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'search','Origin':self.server.origin}
        self.assertEqual(self.get('api/search','POST',body=payload)[0],403)
        self.assertEqual(self.get('api/search','POST',headers=dict(headers,Origin='https://external.example'),body=payload)[0],403)
        status,_,raw=self.get('api/search','POST',headers=headers,body=payload)
        self.assertEqual(status,202)
        sid=json.loads(raw)['search_id']
        self.server.search.thread.join(timeout=5)
        state=json.loads(self.get('api/state')[2])
        self.assertEqual(len(state['state']['searches'][sid]['job_ids']),2)
        self.assertEqual(len(state['rankings']),2)
        self.assertIsNone(state['active_search'])

    def test_search_post_validates_body_and_has_no_submit_api(self):
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'search','Origin':self.server.origin}
        self.assertEqual(self.get('api/search','POST',headers=headers,body='{}')[0],400)
        self.assertEqual(self.get('api/search','POST',headers=headers,body='x'*4097)[0],413)
        self.assertEqual(self.get('api/submit','POST',headers=headers,body='{}')[0],405)
        self.assertEqual(self.ws.read()['jobs'],{})

    def test_settings_routes_reject_cross_site_and_redact_secrets(self):
        payload=json.dumps({'kind':'site','url':'https://careers.example.invalid','username':'fixture','password':'private-fixture-123','allow_login':True,'allow_signup':False})
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'settings','Origin':self.server.origin}
        self.assertEqual(self.get('api/settings','POST',body=payload)[0],403)
        self.assertEqual(self.get('api/settings','POST',headers=dict(headers,Origin='https://evil.invalid'),body=payload)[0],403)
        status,_,raw=self.get('api/settings','POST',headers=headers,body=payload)
        self.assertEqual(status,202)
        for response in [raw,self.get('api/settings')[2],self.get('api/export')[2],self.get('api/state')[2]]:
            self.assertNotIn(b'private-fixture-123',response)
        self.assertTrue(json.loads(raw)['sites']['https://careers.example.invalid']['password_saved'])
        for action in ['telegram-test','telegram-chats','assistance-retry','assistance-resume']:
            self.assertEqual(self.get('api/'+action,'POST',body='{}')[0],403)

    def test_assistance_resume_route_requires_resolution(self):
        jid=self.ws.mutate({'op':'job-add','title':'Fixture','company':'Fixture','description':'Test','source':'Test','url':'https://example.invalid/job'})['job_id']
        self.ws.mutate({'op':'select','job_id':jid})
        self.ws.mutate({'op':'pause','job_id':jid,'reason':'Manual verification','next_action':'Resolve'})
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'assistance-resume','Origin':self.server.origin}
        self.assertEqual(self.get('api/assistance-resume','POST',headers=headers,body=json.dumps({'job_id':jid,'note':''}))[0],400)
        self.assertEqual(self.get('api/assistance-resume','POST',headers=headers,body=json.dumps({'job_id':jid,'note':'Resolved manually'}))[0],202)
        self.assertEqual(self.ws.read()['jobs'][jid]['status'],'Preparing')

    def test_email_controls_require_same_origin_and_offer_no_mail_send_api(self):
        payload=json.dumps({'account':'fixture@example.invalid','enabled':True,'auto_apply':False})
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'email-config','Origin':self.server.origin}
        self.assertEqual(self.get('api/email-config','POST',body=payload)[0],403)
        self.assertEqual(self.get('api/email-config','POST',headers=headers,body=payload)[0],202)
        self.assertTrue(self.ws.read()['email_tracking']['config']['enabled'])
        for route in ['email-record','email-check-start','email-send','email-read']:
            self.assertEqual(self.get('api/'+route,'POST',headers=headers,body='{}')[0],405)
        self.assertEqual(self.get('api/email-apply','POST',body='{}')[0],403)

    def test_primary_portal_request_waits_for_agent_not_public_feeds(self):
        headers={'Content-Type':'application/json','X-CareerPilot-Request':'portal-search','Origin':self.server.origin}
        data=json.dumps({'role':'Data Analyst','location':'Toronto','posted_within':'7'})
        self.assertEqual(self.get('api/portal-search','POST',body=data)[0],403)
        status,_,raw=self.get('api/portal-search','POST',headers=headers,body=data)
        self.assertEqual(status,202)
        run=self.ws.read()['searches'][json.loads(raw)['search_id']]
        self.assertEqual(run['status'],'awaiting_agent')
        self.assertEqual(run['required_sources'],['LinkedIn','Indeed'])
        self.assertTrue(run['external_only'])
        self.assertIsNone(self.server.search.thread)


if __name__ == '__main__':
    unittest.main()
