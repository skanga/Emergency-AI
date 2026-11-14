"""Model recommendations and current preparation defaults."""
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
        self.assertEqual(download.call_args.args[0]['id'], cfg['recommendations']['lightweight'])

    def test_obsolete_choices_are_not_in_catalogue(self):
        cfg = json.loads((ROOT / 'config/models.json').read_text(encoding='utf-8'))
        self.assertFalse({'light', 'standard', 'strong', 'llama3b'} & {m['id'] for m in cfg['models']})

    def test_each_tier_has_a_verified_recommendation(self):
        cfg = json.loads((ROOT / 'config/models.json').read_text(encoding='utf-8'))
        models = {m['id']: m for m in cfg['models']}
        self.assertEqual(set(cfg['recommendations']), {'lightweight', 'balanced', 'larger'})
        self.assertEqual(cfg['default'], cfg['recommendations']['lightweight'])
        self.assertEqual(cfg['models'][0]['id'], cfg['default'])
        self.assertEqual(min(cfg['models'], key=lambda m: m['size_bytes'])['id'], cfg['default'])
        for mid in cfg['recommendations'].values():
            model = models[mid]
            self.assertRegex(model['sha256'], r'^[0-9a-f]{64}$')
            self.assertIn('/resolve/' + model['revision'] + '/', model['url'])
            self.assertGreater(model['size_bytes'], 0)
            self.assertGreater(model['ram_gb'], model['size_bytes'] / 1024**3)
