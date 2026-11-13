"""Model recommendations must preserve previously saved selections."""
import json
from pathlib import Path
import unittest
import tempfile
import contextlib
import io
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ModelCatalogTests(unittest.TestCase):
    def test_new_preparation_uses_recommended_default(self):
        from app import prepare
        cfg = json.loads((ROOT / 'config/models.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as runtime, patch.object(prepare, 'RUNTIME_DIR', runtime), \
                patch.object(prepare, 'get_model', return_value=True) as download, \
                contextlib.redirect_stdout(io.StringIO()):
            prepare.run(zims='none', oses='this', python=False, yes=True, skip_tools=True)
        self.assertEqual(download.call_args.args[0]['id'], cfg['recommendations']['balanced'])

    def test_legacy_ids_keep_their_original_artifacts(self):
        cfg = json.loads((ROOT / 'config/models.json').read_text(encoding='utf-8'))
        original = json.loads((ROOT / 'tests/manual/model_manifest.json').read_text(encoding='utf-8'))[0]
        models = {m['id']: m for m in cfg['models']}
        self.assertEqual(models['standard']['file'], original['file'])
        self.assertEqual(models['standard']['sha256'], original['sha256'])
        for mid, filename in [('light', 'Qwen2.5-1.5B-Instruct-Q4_K_M.gguf'),
                              ('strong', 'Qwen2.5-7B-Instruct-Q4_K_M.gguf'),
                              ('llama3b', 'Llama-3.2-3B-Instruct-Q4_K_M.gguf')]:
            self.assertEqual(models[mid]['file'], filename)

    def test_each_tier_has_a_verified_recommendation(self):
        cfg = json.loads((ROOT / 'config/models.json').read_text(encoding='utf-8'))
        models = {m['id']: m for m in cfg['models']}
        self.assertEqual(set(cfg['recommendations']), {'lightweight', 'balanced', 'larger'})
        self.assertEqual(cfg['default'], cfg['recommendations']['balanced'])
        for mid in cfg['recommendations'].values():
            model = models[mid]
            self.assertRegex(model['sha256'], r'^[0-9a-f]{64}$')
            self.assertIn('/resolve/' + model['revision'] + '/', model['url'])
            self.assertGreater(model['size_bytes'], 0)
            self.assertGreater(model['ram_gb'], model['size_bytes'] / 1024**3)
