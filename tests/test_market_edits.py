import tempfile
import unittest
from pathlib import Path

from test_skill import toolkit
import learning
import market


class MarketTests(unittest.TestCase):
    def test_pay_parsing(self):
        cases = {'Pay: $70K-80K yearly': (70000, 80000, 'year'), '$70-80K': (70000, 80000, 'year'),
                 '$32-38/hr': (32, 38, 'hour'), '$100,000-$130,000/year': (100000, 130000, 'year'),
                 '$50,000�$70,000': (50000, 70000, 'year'), '$75,000 to $90,000': (75000, 90000, 'year'),
                 'Raised $1.1 billion. Pay $84,234, plus': (84234, 84234, 'year')}
        for text, want in cases.items():
            self.assertEqual(market.pay(text)[:3], want, text)
        self.assertIsNone(market.pay('Revenue of $5 and $90-$20'))

    def test_view_counts_skills_and_groups_pay(self):
        state = {'profile': {'skills': ['SQL', 'HTML/CSS'], 'target_roles': ['Data Analyst']}, 'jobs': {
            '1': dict(id='1', title='Data Analyst', description='SQL, CSS and A/B testing. $60,000 - $70,000'),
            '2': dict(id='2', title='Senior Data Analyst', description='SQL and Azure, A/B testing. $80K-90K'),
            '3': dict(id='3', title='Developer', description='Azure only')}}
        view = market.view(state)
        yours = {r['skill']: r['jobs'] for r in view['skills']['yours']}
        self.assertEqual(yours, {'SQL': 2, 'HTML/CSS': 1})
        missing = {r['skill']: r['jobs'] for r in view['skills']['missing']}
        self.assertEqual(missing, {'Azure': 2, 'A/B Testing': 2})
        [row] = view['salary']['by_role']
        self.assertEqual((row['role'], row['n'], row['low_median'], row['high_median']), ('Data Analyst', 2, 70000, 80000))
        self.assertEqual(market.view(state, 'Developer')['jobs_scanned'], 1)


class EditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ws = toolkit.Workspace(Path(self.temp.name) / 'private'); self.ws.initialize()
        sid = self.ws.mutate(dict(op='search-start', role='Analyst', location='Remote'))['search_id']
        self.ws.mutate(dict(op='search-results', search_id=sid, coverage={}, jobs=[dict(
            title='Synthetic Analyst', company='Fixture', url='https://example.invalid/1',
            description='Synthetic fixture', source='A', location='Remote')]))
        self.jid = self.ws.read()['searches'][sid]['job_ids'][0]

    def tearDown(self):
        self.temp.cleanup()

    def edit(self, **extra):
        return self.ws.mutate(dict(op='learning-edit', job_id=self.jid, document='resume', before='Led a team',
                                   after='Coordinated two classmates', candidate_made=True, **extra))

    def test_edit_recorded_and_shown_newest_first(self):
        self.edit(reason='Do not overstate leadership')
        self.ws.mutate(dict(op='learning-edit', job_id=self.jid, document='answer', before='a', after='b', candidate_made=True))
        view = learning.edits(self.ws.read())
        self.assertEqual(view['total'], 2)
        self.assertEqual(view['recent'][0]['document'], 'answer')
        self.assertIsNone(view['recent'][0]['reason'])
        self.assertEqual(view['recent'][1]['reason'], 'Do not overstate leadership')
        self.assertEqual(view['counts'], {'resume': 1, 'answer': 1})

    def test_edit_validation(self):
        for bad in (dict(document='poem'), dict(after='Led a team'), dict(candidate_made=False)):
            data = dict(op='learning-edit', job_id=self.jid, document='resume', before='Led a team',
                        after='Coordinated', candidate_made=True); data.update(bad)
            with self.assertRaises(ValueError):
                self.ws.mutate(data)
        self.assertEqual(learning.edits(self.ws.read())['total'], 0)

    def test_old_state_without_edits_list(self):
        state = self.ws.read(); state['learning'].pop('edits')
        self.assertEqual(learning.edits(state)['total'], 0)


if __name__ == '__main__':
    unittest.main()
