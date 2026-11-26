import contextlib
import importlib.util
import io
import json
import os
import shlex
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch


class UpgradeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('app.upgrade_cli'), 'upgrade CLI not implemented')
        from app import upgrade_cli
        return upgrade_cli

    def report(self, status='available'):
        return {'checked_at': '2026-11-25T00:00:00+00:00', 'components': [
            {'component': 'app', 'status': status, 'installed': {'commit': 'a'*40},
             'candidate': {'commit': 'b'*40, 'identity': 'b'*40}, 'reason': 'test'}]}

    def test_migration_plan_and_apply_dispatch_without_update_discovery(self):
        api = self.api()
        from app import upgrade_migration
        with patch.object(upgrade_migration, 'run', return_value=0) as run, patch.object(api, 'check') as check:
            self.assertEqual(api.main(['--plan-migration','--commit','a'*40,'--output',str(self.root.parent/'plan.json')],root=self.root),0)
            self.assertEqual(run.call_args.args[1].command,'plan-migration')
            self.assertEqual(api.main(['--apply-migration',str(self.root.parent/'plan.json'),'--yes'],root=self.root),0)
            self.assertEqual(run.call_args.args[1].command,'apply-migration')
            check.assert_not_called()

    def test_json_check_does_not_apply(self):
        api = self.api()
        out = io.StringIO()
        with patch.object(api, 'check', return_value=self.report()), patch.object(api, 'apply_record') as apply, contextlib.redirect_stdout(out):
            self.assertEqual(api.main(['--check-updates', '--json'], root=self.root), 0)
        self.assertEqual(json.loads(out.getvalue())['components'][0]['status'], 'available')
        apply.assert_not_called()

    def test_report_identifies_backend_and_installed_python_asset(self):
        api = self.api()
        report = {'checked_at': 'now', 'components': [
            {'component': 'llama', 'status': 'available', 'installed': {'tag': 'b1', 'backend': 'cuda', 'platform': 'linux-x86_64'}, 'candidate': {'identity': 'b2'}, 'reason': 'test'},
            {'component': 'python', 'status': 'manual', 'installed': {'asset': 'cpython-3.12.16+20261110.tar.gz'}, 'candidate': None, 'reason': 'test'}]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            api.show(report)
        self.assertIn('llama [linux-x86_64/cuda]', out.getvalue())
        self.assertIn('cpython-3.12.16+20261110.tar.gz', out.getvalue())

    def test_noninteractive_requires_explicit_selection_and_yes(self):
        api = self.api()
        with patch('sys.stdin.isatty', return_value=False), patch.object(api, 'check', return_value=self.report()), patch.object(api, 'apply_record') as apply, contextlib.redirect_stdout(io.StringIO()):
            self.assertNotEqual(api.main(['--upgrade', '--yes'], root=self.root), 0)
            self.assertNotEqual(api.main(['--upgrade', '--component', 'app'], root=self.root), 0)
            apply.assert_not_called()

    def test_selected_component_is_only_one_applied(self):
        api = self.api()
        result = self.report()
        result['components'].append(dict(result['components'][0], component='model'))
        with patch.object(api, 'check', return_value=result), patch.object(api, 'apply_record', return_value='test-transaction') as apply, patch.object(api, 'ensure_stopped'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.main(['upgrade', '--component', 'app', '--yes'], root=self.root), 0)
        self.assertEqual(apply.call_count, 1)
        self.assertEqual(apply.call_args.args[1]['component'], 'app')

    def test_upgrade_prints_native_retained_recovery_command_with_explicit_root(self):
        api = self.api()
        root = self.root / 'old kit'
        root.mkdir()
        out = io.StringIO()
        with patch.object(api, 'apply_record', return_value='test-transaction'), patch.object(api, 'ensure_stopped'), contextlib.redirect_stdout(out):
            api.perform(root, self.report(), ['app'], yes=True)
        args = [sys.executable, str(root.resolve() / 'runtime/upgrades/test-transaction/recover.py'),
                '--root', str(root.resolve()), '--rollback', 'test-transaction']
        command = subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)
        self.assertIn('Rollback: ' + command, out.getvalue())

    def test_upgrade_scopes_discovery_to_selected_component(self):
        api=self.api()
        report=self.report('current')
        report['components'][0]['component']='llama'
        with patch.object(api,'check',return_value=report) as check, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.main(['upgrade','--component','llama','--yes'],root=self.root),0)
        self.assertEqual(check.call_args.kwargs.get('components'),['llama'])

    def test_default_decline_and_offline_start_continue(self):
        api = self.api()
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value=''), patch.object(api, 'check', return_value=self.report()), patch.object(api, 'apply_record') as apply, contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(api.startup(self.root, {}))
            apply.assert_not_called()
        with patch('sys.stdin.isatty', return_value=True), patch.object(api, 'check', side_effect=OSError('offline')), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(api.startup(self.root, {}))

    def test_noninteractive_and_optout_start_do_no_network(self):
        api = self.api()
        with patch('sys.stdin.isatty', return_value=False), patch.object(api, 'check') as check:
            self.assertFalse(api.startup(self.root, {}))
        check.assert_not_called()
        with patch('sys.stdin.isatty', return_value=True), patch.object(api, 'check') as check:
            self.assertFalse(api.startup(self.root, {'check_updates_on_start': False}))
        check.assert_not_called()

    def test_recent_cache_skips_network_but_explicit_check_does_not(self):
        api = self.api()
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value=''), patch.object(api, 'check', return_value=self.report()) as check, contextlib.redirect_stdout(io.StringIO()):
            api.startup(self.root, {})
            api.startup(self.root, {})
            self.assertEqual(check.call_count, 1)
            api.main(['--check-updates'], root=self.root)
            self.assertEqual(check.call_count, 2)

    def test_emergency_cli_accepts_upgrade_alias_and_help(self):
        result = subprocess.run([sys.executable, 'emergency.py', '--upgrade', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--component', result.stdout)

    def test_start_parser_accepts_offline_override(self):
        import emergency
        with patch.object(sys, 'argv', ['emergency.py', '--no-update-check']), patch.object(emergency, 'cmd_start', return_value=0) as start:
            self.assertEqual(emergency.main(), 0)
        self.assertTrue(start.call_args.args[0].no_update_check)

    def test_adopt_alias_verifies_existing_assets_without_update_check(self):
        api = self.api()
        from app import upgrade_inventory
        result = {'transaction_id': 'abc', 'adopted': [{'component': 'model', 'path': 'models/test.gguf'}], 'unknown': []}
        with patch.object(upgrade_inventory, 'adopt', return_value=result) as adopt, patch.object(api, 'check') as check, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.main(['--adopt', '--component', 'model'], root=self.root), 0)
        adopt.assert_called_once()
        check.assert_not_called()

    def test_external_updater_checks_explicit_target_without_overlay(self):
        api = self.api()
        target = self.root / 'old kit'
        target.mkdir()
        with patch.object(api, 'check', return_value=self.report()) as check, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.main(['--check-updates', '--root', str(target)], root=self.root), 0)
        self.assertEqual(check.call_args.args[0], target.resolve())

    def test_custom_archive_does_not_block_available_managed_archive(self):
        api = self.api()
        report = self.report()
        report['components'][0]['component'] = 'kiwix-data'
        report['components'].append({'component': 'kiwix-data', 'status': 'unknown', 'candidate': None, 'reason': 'custom', 'installed': {'path': 'zim/custom.zim'}})
        with patch.object(api, 'check', return_value=report), patch.object(api, 'apply_record', return_value='id') as apply, patch.object(api, 'ensure_stopped'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.main(['upgrade', '--component', 'kiwix-data', '--yes'], root=self.root), 0)
        self.assertEqual(apply.call_count, 1)


if __name__ == '__main__':
    unittest.main()
