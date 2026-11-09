"""Source and public-preview constraints for the unified repository."""
import os,unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
class RepoTests(unittest.TestCase):
    def test_pages_contains_saved_cases(self):
        doc=(ROOT/'docs/index.html').read_text(encoding='utf-8')
        for name in ('Cairo','Mauritania','Queens'):self.assertIn(name,doc)
    def test_public_quality_route(self):
        from backend.server import app
        r=TestClient(app).get('/quality')
        self.assertEqual(r.status_code,200)
        self.assertIn('text/html',r.headers['content-type'])
        self.assertIn('Mauritania',r.text)
    def test_model_manifest_matches_importer(self):
        import json
        from backend.assets import SHA,CHECKPOINT
        m=json.loads((ROOT/'models/model-manifest.json').read_text())
        self.assertEqual(m['checkpoint_sha256'],SHA)
        self.assertEqual(m['checkpoint_relative_path'],CHECKPOINT)
    def test_preview_disables_writes(self):
        import backend.server as server
        original=server.PREVIEW
        try:
            server.PREVIEW=True
            cli=TestClient(server.app)
            self.assertIsNone(cli.get('/api/status').json()['workspace'])
            r=cli.post('/api/analyze',json={})
            self.assertEqual(r.status_code,403)
        finally:server.PREVIEW=original
if __name__=='__main__':unittest.main()
