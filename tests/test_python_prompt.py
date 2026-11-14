"""Setup distinguishes reusable portable Python from missing platforms."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import prepare


class PythonPromptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        installed = self.root / 'python/windows-x86_64'
        (installed / 'python').mkdir(parents=True)
        (installed / 'python/python.exe').write_bytes(b'python')
        (installed / 'installation.json').write_text(json.dumps({'complete': True}))

    def test_existing_runtime_is_reused_without_question(self):
        output = io.StringIO()
        with patch.object(prepare, 'RUNTIME_DIR', str(self.root)), \
                patch('builtins.input') as ask, contextlib.redirect_stdout(output):
            self.assertTrue(prepare.choose_portable_python(['windows-x86_64'], 'en'))
        ask.assert_not_called()
        self.assertIn('Reusing', output.getvalue())
        self.assertIn('No Python download', output.getvalue())

    def test_only_missing_platforms_are_offered(self):
        output = io.StringIO()
        with patch.object(prepare, 'RUNTIME_DIR', str(self.root)), \
                patch('builtins.input', return_value='y') as ask, contextlib.redirect_stdout(output):
            self.assertTrue(prepare.choose_portable_python(['windows-x86_64', 'linux-arm64'], 'en'))
        question = ask.call_args.args[0]
        self.assertIn('linux-arm64', question)
        self.assertNotIn('windows-x86_64', question)
        self.assertIn('windows-x86_64', output.getvalue())

    def test_declining_does_not_remove_installed_python(self):
        with patch.object(prepare, 'RUNTIME_DIR', str(self.root)), \
                patch('builtins.input', return_value='n'), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(prepare.choose_portable_python(['windows-x86_64', 'linux-arm64'], 'en'))
        self.assertTrue((self.root / 'python/windows-x86_64/python/python.exe').is_file())

    def test_wizard_skips_python_question_for_installer_runtime(self):
        with patch.object(prepare, 'RUNTIME_DIR', str(self.root)), \
                patch.object(prepare, 'platform_key', return_value='windows-x86_64'), \
                patch.object(prepare, 'github_latest_assets') as metadata, \
                patch('builtins.input', side_effect=['', 'none', 'none', 'this', 'y']) as ask, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(prepare.run(), 0)
        self.assertEqual(ask.call_count, 5)
        metadata.assert_not_called()
