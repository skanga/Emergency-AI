import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class AppUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'kit'
        self.root.mkdir()
        self.fresh = self.base / 'fresh'
        self.fresh.mkdir()

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('app.upgrade_app'), 'application upgrade not implemented')
        from app import upgrade_app
        return upgrade_app

    def write(self, root, name, text):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def baseline(self, api):
        files = api.file_manifest(self.root)
        self.write(self.root, 'runtime/installation.json', json.dumps({'schema_version': 1, 'app': {'commit': 'a' * 40, 'files': files}}))

    def test_standalone_preserves_personal_content_and_rolls_back_owned_files(self):
        api = self.api()
        self.write(self.root, 'app/example.py', 'old = 1')
        self.write(self.root, 'obsolete.txt', 'old')
        self.baseline(api)
        self.write(self.root, 'knowledge/extra/personal.txt', 'personal')
        self.write(self.root, 'config/settings.local.json', '{"custom": true}')
        self.write(self.fresh, 'app/example.py', 'new = 2')
        tx = api.apply_standalone(self.root, self.fresh, 'b' * 40, verify=lambda: None)
        self.assertFalse((self.root / 'obsolete.txt').exists())
        self.assertEqual((self.root / 'knowledge/extra/personal.txt').read_text(), 'personal')
        from upgrade_recovery import rollback
        rollback(self.root, tx)
        self.assertEqual((self.root / 'app/example.py').read_text(), 'old = 1')
        self.assertEqual((self.root / 'obsolete.txt').read_text(), 'old')
        self.assertEqual(json.loads((self.root / 'config/settings.local.json').read_text()), {'custom': True})

    def test_modified_bundled_knowledge_blocks_entire_update(self):
        api = self.api()
        self.write(self.root, 'knowledge/en/guide.md', 'original')
        self.baseline(api)
        self.write(self.root, 'knowledge/en/guide.md', 'locally reviewed')
        self.write(self.fresh, 'knowledge/en/guide.md', 'new official')
        with self.assertRaisesRegex(ValueError, 'modified'):
            api.apply_standalone(self.root, self.fresh, 'b' * 40)
        self.assertEqual((self.root / 'knowledge/en/guide.md').read_text(), 'locally reviewed')

    def test_unknown_baseline_and_untracked_collision_refused(self):
        api = self.api()
        self.write(self.root, 'user.txt', 'mine')
        self.write(self.fresh, 'user.txt', 'upstream')
        with self.assertRaisesRegex(ValueError, 'baseline'):
            api.apply_standalone(self.root, self.fresh, 'b' * 40)
        self.baseline(api)
        self.write(self.root, 'new.txt', 'mine')
        self.write(self.fresh, 'new.txt', 'upstream')
        with self.assertRaisesRegex(ValueError, 'collision'):
            api.apply_standalone(self.root, self.fresh, 'b' * 40)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root)] + list(args), text=True, stderr=subprocess.STDOUT).strip()

    def git_fixture(self):
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.write(self.root, 'a.py', 'a=1')
        self.git('add', '.')
        self.git('commit', '-m', 'before')
        old = self.git('rev-parse', 'HEAD')
        self.write(self.root, 'a.py', 'a=2')
        self.git('commit', '-am', 'after')
        new = self.git('rev-parse', 'HEAD')
        self.git('reset', '--keep', old)
        return old, new

    def test_git_fast_forward_and_offline_rollback(self):
        api = self.api()
        old, new = self.git_fixture()
        tx = api.apply_git(self.root, new, verify=lambda: None)
        self.assertEqual(self.git('rev-parse', 'HEAD'), new)
        from upgrade_recovery import rollback
        rollback(self.root, tx)
        self.assertEqual(self.git('rev-parse', 'HEAD'), old)
        self.assertEqual((self.root / 'a.py').read_text(), 'a=1')

    def test_git_dirty_tree_is_not_stashed_or_reset(self):
        api = self.api()
        old, new = self.git_fixture()
        self.write(self.root, 'a.py', 'local=3')
        with self.assertRaisesRegex(ValueError, 'modified'):
            api.apply_git(self.root, new)
        self.assertEqual(self.git('rev-parse', 'HEAD'), old)
        self.assertEqual((self.root / 'a.py').read_text(), 'local=3')

    def test_git_update_refuses_ignored_personal_file_collision(self):
        api = self.api()
        old, new = self.git_fixture()
        self.write(self.root, '.gitignore', 'personal.txt\n')
        self.git('add', '.gitignore')
        self.git('commit', '-m', 'ignore personal')
        before = self.git('rev-parse', 'HEAD')
        self.write(self.root, 'personal.txt', 'upstream')
        self.git('add', '-f', 'personal.txt')
        self.git('commit', '-m', 'add collision')
        candidate = self.git('rev-parse', 'HEAD')
        self.git('reset', '--keep', before)
        self.write(self.root, 'personal.txt', 'private')
        with self.assertRaisesRegex(ValueError, 'collision'):
            api.apply_git(self.root, candidate, verify=lambda: None)
        self.assertEqual((self.root / 'personal.txt').read_text(), 'private')

    def test_git_rollback_refuses_new_ignored_file_collision(self):
        api = self.api()
        self.git_fixture()
        self.write(self.root, '.gitignore', 'personal.txt\n')
        self.write(self.root, 'personal.txt', 'old tracked')
        self.git('add', '.gitignore')
        self.git('add', '-f', 'personal.txt')
        self.git('commit', '-m', 'old file')
        before = self.git('rev-parse', 'HEAD')
        self.git('rm', 'personal.txt')
        self.git('commit', '-m', 'remove file')
        candidate = self.git('rev-parse', 'HEAD')
        self.git('reset', '--keep', before)
        tx = api.apply_git(self.root, candidate, verify=lambda: None)
        self.write(self.root, 'personal.txt', 'new private')
        from upgrade_recovery import rollback
        with self.assertRaisesRegex(ValueError, 'collision'):
            rollback(self.root, tx)
        self.assertEqual((self.root / 'personal.txt').read_text(), 'new private')

    def test_interrupted_git_checkout_recovers_known_partial_state(self):
        api = self.api()
        old, new = self.git_fixture()
        original = api.git
        def interrupt(root, *args):
            if 'merge' in args:
                self.write(self.root, 'a.py', 'a=2')
                raise KeyboardInterrupt()
            return original(root, *args)
        with patch.object(api, 'git', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            api.apply_git(self.root, new, verify=lambda: None)
        from upgrade_recovery import pending, rollback
        transactions = pending(self.root)
        self.assertEqual(len(transactions), 1)
        rollback(self.root, transactions[0])
        self.assertEqual(self.git('rev-parse', 'HEAD'), old)
        self.assertEqual((self.root / 'a.py').read_text(), 'a=1')

    def test_git_allows_unchanged_protected_tracked_readme(self):
        api = self.api()
        self.git_fixture()
        self.write(self.root, 'knowledge/extra/README.md', 'personal guide instructions')
        self.git('add', 'knowledge/extra/README.md')
        self.git('commit', '-m', 'readme')
        before = self.git('rev-parse', 'HEAD')
        self.write(self.root, 'a.py', 'a=3')
        self.git('commit', '-am', 'new app')
        candidate = self.git('rev-parse', 'HEAD')
        self.git('reset', '--keep', before)
        api.apply_git(self.root, candidate, verify=lambda: None)
        self.assertEqual((self.root / 'a.py').read_text(), 'a=3')

    def test_git_rejects_rename_out_of_protected_knowledge(self):
        api = self.api()
        self.git_fixture()
        self.write(self.root, 'knowledge/extra/README.md', 'personal instructions')
        self.git('add', 'knowledge/extra/README.md')
        self.git('commit', '-m', 'readme')
        before = self.git('rev-parse', 'HEAD')
        self.git('mv', 'knowledge/extra/README.md', 'README.md')
        self.git('commit', '-m', 'move protected file')
        candidate = self.git('rev-parse', 'HEAD')
        self.git('reset', '--keep', before)
        with self.assertRaisesRegex(ValueError, 'Protected'):
            api.apply_git(self.root, candidate, verify=lambda: None)

    def test_git_mode_only_change_rolls_back_cleanly(self):
        api = self.api()
        self.git_fixture()
        before = self.git('rev-parse', 'HEAD')
        (self.root / 'a.py').chmod(0o755)
        self.git('commit', '-am', 'executable')
        candidate = self.git('rev-parse', 'HEAD')
        self.git('reset', '--keep', before)
        tx = api.apply_git(self.root, candidate, verify=lambda: None)
        from upgrade_recovery import rollback
        rollback(self.root, tx)
        self.assertEqual((self.root / 'a.py').stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=no'), '')

    def test_git_index_remains_locked_during_file_restoration(self):
        api = self.api()
        old, new = self.git_fixture()
        tx = api.apply_git(self.root, new, verify=lambda: None)
        import upgrade_recovery as recovery
        original = recovery._activate
        attempts = []
        def concurrent_add(source, target):
            if Path(target) == self.root / 'a.py':
                self.write(self.root, 'user.txt', 'staged user content')
                result = subprocess.run(['git', '-C', str(self.root), 'add', 'user.txt'],
                                        capture_output=True)
                attempts.append(result.returncode)
            return original(source, target)
        with patch.object(recovery, '_activate', side_effect=concurrent_add):
            recovery.rollback(self.root, tx)
        self.assertEqual(len(attempts), 1)
        self.assertNotEqual(attempts[0], 0, 'Git add must respect the recovery index lock')
        self.assertFalse((self.root / '.git/index.lock').exists())

    def test_git_existing_index_lock_preserved_before_recovery(self):
        api = self.api()
        old, new = self.git_fixture()
        tx = api.apply_git(self.root, new, verify=lambda: None)
        lock = self.root / '.git/index.lock'
        lock.write_bytes(b'other operation')
        from upgrade_recovery import rollback
        with self.assertRaisesRegex(RuntimeError, 'locked'):
            rollback(self.root, tx)
        self.assertEqual(lock.read_bytes(), b'other operation')
        self.assertEqual((self.root / 'a.py').read_text(), 'a=2')
        self.assertEqual(self.git('rev-parse', 'HEAD'), new)

    def test_git_recovery_releases_lock_after_preflight_failure(self):
        api = self.api()
        old, new = self.git_fixture()
        tx = api.apply_git(self.root, new, verify=lambda: None)
        (self.root / 'a.py').write_text('private edit')
        from upgrade_recovery import rollback
        with self.assertRaisesRegex(ValueError, 'changed'):
            rollback(self.root, tx)
        self.assertFalse((self.root / '.git/index.lock').exists())
        self.assertEqual((self.root / 'a.py').read_text(), 'private edit')


if __name__ == '__main__':
    unittest.main()
