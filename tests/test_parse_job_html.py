import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'parse_job_html', Path(__file__).resolve().parents[1] /
    'skills/careerpilot/scripts/parse_job_html.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


class OfflineParserTests(unittest.TestCase):
    def test_graph_extracts_only_posting_fields(self):
        graph = {'@graph': [{'@type': 'Organization'}, {
            '@type': ['Thing', 'JobPosting'], 'title': 'Analyst',
            'datePosted': '2026-01-01', 'employer_verified': True,
        }]}
        self.assertEqual(list(parser.postings(graph)), [
            {'title': 'Analyst', 'datePosted': '2026-01-01'},
        ])
