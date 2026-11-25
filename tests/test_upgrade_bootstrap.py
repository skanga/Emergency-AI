"""Exercise bootstrap isolation with disposable installation roots."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import upgrade_recovery as recovery

ROOT = Path(__file__).resolve().parents[1]


class UpgradeBootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copy2(ROOT / 'upgrade_recovery.py', self.root / 'upgrade_recovery.py')

    def run_bootstrap(self, *args):
        return subprocess.run([sys.executable, str(self.root / 'upgrade_recovery.py'), '--launch', *args],
                              capture_output=True, text=True, timeout=10)

    def test_lock_blocks_before_app_is_parsed(self):
        (self.root / 'emergency.py').write_text('invalid python !!!')
        with recovery.maintenance_lock(self.root):
            result = self.run_bootstrap('status')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Another maintenance', result.stdout)
        self.assertNotIn('SyntaxError', result.stderr)

    def test_pending_blocks_direct_python_before_app_imports(self):
        shutil.copy2(ROOT / 'emergency.py', self.root / 'emergency.py')
        transaction = recovery.Transaction(self.root, 'app')
        transaction.data['state'] = 'activating'
        transaction.save()
        result = subprocess.run([sys.executable, str(self.root / 'emergency.py'), 'status'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Recover interrupted', result.stdout)
        self.assertNotIn('ModuleNotFoundError', result.stderr)

    def test_script_module_identity_allows_exclusive_lock_reuse(self):
        (self.root / 'emergency.py').write_text(
            'from upgrade_recovery import maintenance_lock\n'
            'from pathlib import Path\n'
            'with maintenance_lock(Path(__file__).parent, reuse=True):\n'
            '    print("lease reused")\n')
        result = self.run_bootstrap('prepare')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('lease reused', result.stdout)

    def test_question_text_does_not_select_maintenance_mode(self):
        (self.root / 'emergency.py').write_text('print("question accepted")\n')
        with recovery.maintenance_lock(self.root, shared=True):
            result = self.run_bootstrap('ask', 'upgrade')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_backup_helper_recovers_without_root_app_or_helper(self):
        target = self.root / 'original'
        target.write_text('old')
        fresh = self.root / 'fresh'
        fresh.write_text('new')
        transaction = recovery.Transaction(self.root, 'app')
        transaction.apply({'original': fresh})
        (self.root / 'upgrade_recovery.py').unlink()
        (self.root / 'config').mkdir()
        (self.root / 'config/settings.json').write_text(json.dumps(
            {'web_port': 0, 'llm_port': 0, 'kiwix_port': 0}))
        result = subprocess.run([sys.executable, str(transaction.folder / 'recover.py'),
                                 '--root', str(self.root), '--rollback', transaction.id],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(target.read_text(), 'old')

    def test_interactive_default_decline_still_hands_off_to_fresh_process(self):
        from app import upgrade_cli
        arguments = ['start', '--port', '8123', '--no-browser']
        with patch('sys.stdin.isatty', return_value=True), \
                patch.object(upgrade_cli, 'startup', return_value=False) as startup, \
                patch.object(recovery.os, 'execv', side_effect=SystemExit(23)) as execute:
            with self.assertRaises(SystemExit):
                recovery.launch(arguments, root=self.root)
        startup.assert_called_once()
        self.assertEqual(execute.call_args.args,
                         (sys.executable, [sys.executable, str(self.root / 'emergency.py'),
                                           *arguments, '--no-update-check']))
        self.assertNotIn(str(self.root.resolve()), recovery._HELD_LOCKS)


if __name__ == '__main__':
    unittest.main()
