import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from test_skill import toolkit, packager
import release_tools


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ws = toolkit.Workspace(self.root / 'candidate')

    def test_demo_backup_restore_and_guarded_delete(self):
        release_tools.demo(self.ws)
        archive = self.root / 'private.zip'
        release_tools.backup(self.ws, archive)
        restored = toolkit.Workspace(self.root / 'restored')
        release_tools.restore(restored, archive)
        self.assertEqual(restored.read(), self.ws.read())
        with self.assertRaises(ValueError):
            release_tools.delete(restored, str(self.ws.root))
        release_tools.delete(restored, str(restored.root))
        self.assertFalse(restored.root.exists())
        self.assertTrue(self.ws.root.exists())

    def test_unsafe_archive_and_wrong_workspace(self):
        archive = self.root / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('../escape', 'unsafe')
        with self.assertRaises(ValueError):
            release_tools.restore(self.ws, archive)
        self.assertFalse(self.ws.root.exists())

    def test_setup_regional_portals_and_metrics(self):
        release_tools.demo(self.ws)
        self.ws.mutate(dict(op='setup-step', step='gmail', status='skipped'))
        self.ws.mutate(dict(op='international-config', country='GB', currency='GBP',
                            portals=['Indeed'], date_format='dmy'))
        result = self.ws.mutate(dict(op='portal-search-start', role='Analyst', location='London'))
        state = self.ws.read()
        self.assertEqual(state['setup']['gmail'], 'skipped')
        self.assertEqual(state['searches'][result['search_id']]['required_sources'], ['Indeed'])
        path = self.root / 'metrics.json'
        with self.assertRaises(ValueError):
            release_tools.metrics(self.ws, path, False)
        release_tools.metrics(self.ws, path, True)
        self.assertEqual(json.loads(path.read_text())['status_counts'], {})
        self.assertNotIn('Demo', path.read_text())
        self.assertEqual(release_tools.doctor(self.ws)['checks']['gmail']['status'], 'unknown')

    def test_release_matches_explicit_manifest(self):
        archive = self.root / 'release.zip'
        packager.package(archive)
        expected = (packager.ROOT / 'tools' / 'skill-files.txt').read_text().splitlines()
        with zipfile.ZipFile(archive) as source:
            self.assertEqual(set(source.namelist()), {'careerpilot/' + name for name in expected})
