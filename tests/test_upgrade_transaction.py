import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.spec = importlib.util.find_spec('upgrade_recovery')

    def api(self):
        self.assertIsNotNone(self.spec, 'offline upgrade recovery is not implemented')
        import upgrade_recovery
        return upgrade_recovery

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)
        return p

    def test_llama_leaf_link_round_trip_and_parent_link_rejection(self):
        api = self.api()
        original = self.write('runtime/lib.so.1', 'old library')
        link = self.root/'runtime/lib.so'
        link.symlink_to('lib.so.1')
        fresh = self.write('staged/new', 'new library')
        tx = api.Transaction(self.root, 'llama', preserve_file_links=True)
        tx.apply({'runtime/lib.so': fresh, 'runtime/lib.so.1': None})
        self.assertFalse(link.is_symlink())
        api.rollback(self.root, tx.id)
        self.assertTrue(link.is_symlink())
        self.assertEqual(str(link.readlink()), 'lib.so.1')
        self.assertEqual(link.read_text(), 'old library')
        (self.root/'alias').symlink_to(self.root/'runtime', target_is_directory=True)
        other = api.Transaction(self.root, 'llama', preserve_file_links=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            other.apply({'alias/lib.so': fresh})

    def test_leaf_link_backup_tampering_blocks_rollback(self):
        api = self.api()
        self.write('runtime/lib.so.1', 'old library')
        link = self.root/'runtime/lib.so'
        link.symlink_to('lib.so.1')
        fresh = self.write('staged/new', 'new library')
        tx = api.Transaction(self.root, 'llama', preserve_file_links=True)
        tx.apply({'runtime/lib.so': fresh})
        backup = tx.folder/'before/runtime/lib.so'
        backup.unlink(); backup.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'backup'):
            api.rollback(self.root, tx.id)
        self.assertEqual(link.read_text(), 'new library')

    def test_failed_health_check_restores_original_leaf_link(self):
        api = self.api()
        self.write('runtime/lib.so.1', 'old library')
        link = self.root/'runtime/lib.so'
        link.symlink_to('lib.so.1')
        fresh = self.write('staged/new', 'new library')
        tx = api.Transaction(self.root, 'llama', preserve_file_links=True)
        with self.assertRaisesRegex(RuntimeError, 'health'):
            tx.apply({'runtime/lib.so': fresh}, verify=lambda: (_ for _ in ()).throw(RuntimeError('health')))
        self.assertTrue(link.is_symlink())
        self.assertEqual(str(link.readlink()), 'lib.so.1')
        self.assertEqual(json.loads((tx.folder/'journal.json').read_text())['state'], 'rolled_back')

    def test_activation_and_offline_rollback_preserve_unrelated_files(self):
        api = self.api()
        self.write('app/code.py', 'old')
        self.write('knowledge/extra/my.txt', 'personal')
        fresh = self.write('staged/new', 'new')
        tx = api.Transaction(self.root, 'app')
        tx.apply({'app/code.py': fresh, 'app/added.py': fresh})
        self.assertEqual((self.root / 'app/code.py').read_text(), 'new')
        api.rollback(self.root, tx.id)
        self.assertEqual((self.root / 'app/code.py').read_text(), 'old')
        self.assertFalse((self.root / 'app/added.py').exists())
        self.assertEqual((self.root / 'knowledge/extra/my.txt').read_text(), 'personal')
        self.assertTrue((tx.folder / 'recover.py').exists())

    def test_failed_health_check_restores_deleted_and_changed_files(self):
        api = self.api()
        self.write('old.zim', 'old data')
        fresh = self.write('staged/new', 'new data')
        tx = api.Transaction(self.root, 'kiwix-data')
        def fail():
            raise ValueError('bad health')
        with self.assertRaisesRegex(ValueError, 'bad health'):
            tx.apply({'old.zim': None, 'new.zim': fresh}, verify=fail)
        self.assertEqual((self.root / 'old.zim').read_text(), 'old data')
        self.assertFalse((self.root / 'new.zim').exists())

    def test_rollback_refuses_later_user_edits_before_any_restore(self):
        api = self.api()
        self.write('a', 'old a')
        self.write('b', 'old b')
        fresh = self.write('staged/new', 'new')
        tx = api.Transaction(self.root, 'app')
        tx.apply({'a': fresh, 'b': fresh})
        self.write('b', 'user edit')
        with self.assertRaisesRegex(ValueError, 'changed'):
            api.rollback(self.root, tx.id)
        self.assertEqual((self.root / 'a').read_text(), 'new')
        self.assertEqual((self.root / 'b').read_text(), 'user edit')

    def test_rejects_escape_git_and_symlink_targets(self):
        api = self.api()
        fresh = self.write('staged/new', 'new')
        for name in ('../escape', '/absolute', '.git/config', 'runtime/upgrades/evil'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                api.Transaction(self.root, 'app').apply({name: fresh})
        (self.root / 'link').symlink_to(self.root / 'staged', target_is_directory=True)
        with self.assertRaises(ValueError):
            api.Transaction(self.root, 'app').apply({'link/new': fresh})

    def test_interrupted_operation_recovered_with_retained_journal(self):
        api = self.api()
        self.write('a', 'old')
        fresh = self.write('staged/new', 'new')
        tx = api.Transaction(self.root, 'app')
        original = api._activate
        def interrupt(source, target):
            if pathlib.Path(target) == self.root / 'a':
                raise KeyboardInterrupt()
            return original(source, target)
        with patch.object(api, '_activate', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                tx.apply({'a': fresh})
        self.assertEqual(len(api.pending(self.root)), 1)
        api.rollback(self.root, tx.id)
        self.assertEqual((self.root / 'a').read_text(), 'old')
        self.assertEqual(api.pending(self.root), [])

    def test_lock_excludes_second_maintenance_operation(self):
        api = self.api()
        with api.maintenance_lock(self.root):
            with self.assertRaisesRegex(RuntimeError, 'maintenance'):
                with api.maintenance_lock(self.root):
                    pass

    def test_corrupt_backup_refuses_rollback(self):
        api = self.api()
        self.write('a', 'old')
        fresh = self.write('staged/new', 'new')
        tx = api.Transaction(self.root, 'app')
        tx.apply({'a': fresh})
        (tx.folder / 'before' / 'a').write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'backup'):
            api.rollback(self.root, tx.id)
        self.assertEqual((self.root / 'a').read_text(), 'new')

    def test_mode_only_upgrade_and_rollback(self):
        api = self.api()
        target = self.write('tool', 'same bytes')
        target.chmod(0o644)
        fresh = self.write('staged/tool', 'same bytes')
        fresh.chmod(0o755)
        tx = api.Transaction(self.root, 'app')
        tx.apply({'tool': fresh})
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)
        api.rollback(self.root, tx.id)
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)

    def test_rollback_preserves_later_permission_changes(self):
        api = self.api()
        target = self.write('tool', 'old')
        target.chmod(0o644)
        fresh = self.write('staged/tool', 'new')
        fresh.chmod(0o755)
        tx = api.Transaction(self.root, 'app')
        tx.apply({'tool': fresh})
        target.chmod(0o700)
        with self.assertRaisesRegex(ValueError, 'changed'):
            api.rollback(self.root, tx.id)
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)


if __name__ == '__main__':
    unittest.main()
