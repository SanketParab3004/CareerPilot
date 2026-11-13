import tempfile
import unittest
from pathlib import Path

from test_skill import toolkit
import interviews


class InterviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = toolkit.Workspace(Path(self.temp.name))
        self.ws.initialize()
        self.job = self.op('job-add', title='Analyst', company='Fixture',
                           description='SQL required', source='Synthetic',
                           url='https://example.invalid/role')['job_id']

    def op(self, op, **data):
        return self.ws.mutate(dict(op=op, **data))

    def test_story_sources_and_practice_retry(self):
        self.op('profile-save', profile={'experience': 'Built SQL reports'})
        parts = dict(situation='Reporting backlog', task='Create reports',
                     action='Built SQL reports', result='Delivered the reports')
        ref = dict(kind='profile', pointer='/experience', quote='Built SQL reports')
        story = self.op('story-save', title='Reports', **parts, skills=['SQL'],
                        competencies=['Delivery'], candidate_confirmation='Synthetic candidate verified all parts',
                        sources={key: [ref] for key in parts})
        self.assertEqual(story['sources']['action'][0]['fact'], 'Built SQL reports')
        with self.assertRaises(ValueError):
            self.op('mock-start', round_type='technical', mode='voice', questions=['Explain joins'])
        mock = self.op('mock-start', round_type='technical', questions=['Explain joins'])
        for index in (1, 2):
            attempt = self.op('mock-answer', mock_id=mock['id'], question_index=0,
                              answer='Synthetic answer', score=3, score_reason='Basic reasoning',
                              feedback='Compare outer joins', next_drill='Try a missing row')
            self.assertEqual(attempt['attempt'], index)

    def test_prep_requires_submission_and_binds_exact_job(self):
        with self.assertRaises(ValueError):
            self.op('prep-pack', job_id=self.job, round='Screen', preparation='Practice SQL')
        self.op('manual-submitted', job_id=self.job, applied_at='2026-01-01T00:00:00Z',
                evidence='Synthetic manual confirmation')
        pack = self.op('prep-pack', job_id=self.job, round='Screen', preparation='Practice SQL',
                       submitted_versions_evidence='Synthetic candidate confirms no attachment')
        self.assertEqual(pack['posting']['description'], 'SQL required')
        self.assertEqual(pack['document_versions'], [])

    def test_dated_research_event_drafts_and_offers(self):
        source = dict(url='https://example.invalid/report', publisher='Fixture',
                      accessed_on='2026-01-01', evidence='Synthetic table')
        brief = self.op('company-brief', job_id=self.job, claims=[
            dict(claim='Uses SQL', relevance='Role', source=source)])
        self.assertEqual(brief['claims'][0]['source']['accessed_on'], '2026-01-01')
        base = dict(location='Fixture city', currency='USD', period='year', low='100', high='200')
        self.op('salary-research', **base, source=source, role='Analyst',
                level='Junior', compensation_basis='Base')
        offer = self.op('offer-record', job_id=self.job, label='First offer', evidence='Synthetic letter', base=base)
        self.assertEqual(interviews.view(self.ws.read())['offer_comparison'][0]['base']['high'], '200')
        event = self.op('interview-event', job_id=self.job, round='Screen',
                        start='2026-01-02T12:00:00-05:00', end='2026-01-02T12:30:00-05:00',
                        evidence='Synthetic invite', reminder_minutes=30)
        self.assertEqual(event['status'], 'planned')
        self.assertTrue(event['remind_at'].endswith('+00:00'))
        self.op('interview-note', job_id=self.job, event_id=event['id'], observations='SQL discussion',
                follow_up='Review joins', evidence='Synthetic candidate recollection')
        for kind, target in [('thank-you', event), ('negotiation', offer)]:
            draft = self.op('interview-draft', job_id=self.job, target_id=target['id'], kind=kind,
                            recipient='Fixture', subject='Draft', body='Synthetic')
            self.assertEqual(draft['status'], 'draft')

    def test_skill_plan_uses_recorded_gaps(self):
        self.op('evaluate', job_id=self.job, evaluation=dict(score=50, strengths=[],
                gaps=['SQL'], unknowns=[], evidence=['Posting requires SQL'], recommendation='Review', rationale='Synthetic assessment'))
        step = dict(gap='SQL', practice='Build a join', deliverable='Query',
                    success_check='Correct result', target_date='2027-01-01')
        plan = self.op('skill-plan', steps=[step])
        self.assertEqual(plan['steps'][0]['evidence'][0]['job_id'], self.job)
        with self.assertRaises(ValueError):
            self.op('skill-plan', steps=[dict(step, gap='Invented')])
