import json
import tempfile
import unittest
from pathlib import Path
from app import upgrade_app
from upgrade_recovery import rollback


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'kit'; self.root.mkdir()
        self.fresh = self.base/'fresh'; self.fresh.mkdir()
        self.write(self.root, 'app/code.py', 'value = 1')
        self.write(self.root, 'config/settings.json', '{"local":true}')
        self.write(self.root, 'knowledge/guide.txt', 'local guide')
        self.write(self.root, 'notes.txt', 'personal')
        self.write(self.fresh, 'app/code.py', 'value = 2')
        self.write(self.fresh, 'app/new.py', 'value = 3')
        self.write(self.fresh, 'config/settings.json', '{}')
        self.write(self.fresh, 'knowledge/guide.txt', 'publisher guide')
        self.commit = 'a'*40

    def write(self, root, name, text):
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)

    def api(self):
        from app import upgrade_migration
        return upgrade_migration

    def test_sparse_modified_install_migrates_and_rolls_back(self):
        api=self.api(); plan=api.build_plan(self.root, self.fresh, self.commit)
        self.assertEqual(plan['files']['app/code.py']['action'], 'replace')
        self.assertEqual(plan['files']['app/new.py']['action'], 'add')
        self.assertEqual(plan['files']['config/settings.json']['action'], 'preserve')
        tx=api.apply_plan(self.root,self.fresh,plan,verify=lambda:None)
        self.assertEqual((self.root/'app/code.py').read_text(),'value = 2')
        self.assertEqual((self.root/'knowledge/guide.txt').read_text(),'local guide')
        self.assertEqual((self.root/'config/settings.json').read_text(),'{"local":true}')
        self.assertEqual((self.root/'notes.txt').read_text(),'personal')
        manifest=json.loads((self.root/'runtime/installation.json').read_text())['app']
        self.assertNotIn('knowledge/guide.txt',manifest['files'])
        self.assertIn('knowledge/guide.txt',manifest['preserved_files'])
        rollback(self.root,tx)
        self.assertEqual((self.root/'app/code.py').read_text(),'value = 1')
        self.assertFalse((self.root/'app/new.py').exists())
        self.assertFalse((self.root/'runtime/installation.json').exists())

    def test_stale_or_tampered_plan_is_rejected(self):
        api=self.api();plan=api.build_plan(self.root,self.fresh,self.commit)
        self.write(self.root,'app/code.py','value = 4')
        with self.assertRaisesRegex(ValueError,'changed|match'):
            api.apply_plan(self.root,self.fresh,plan,verify=lambda:None)
        plan=api.build_plan(self.root,self.fresh,self.commit)
        plan['files']['app/code.py']['after']='f'*64
        with self.assertRaisesRegex(ValueError,'changed|match'):
            api.apply_plan(self.root,self.fresh,plan,verify=lambda:None)

    def test_git_and_already_owned_installations_rejected(self):
        api=self.api(); (self.root/'.git').mkdir()
        with self.assertRaises(ValueError): api.build_plan(self.root,self.fresh,self.commit)
        (self.root/'.git').rmdir()
        self.write(self.root,'runtime/installation.json',json.dumps({'app':{'commit':self.commit,'files':{}}}))
        with self.assertRaises(ValueError): api.build_plan(self.root,self.fresh,self.commit)

    def test_future_upgrade_preserves_migrated_local_content(self):
        api=self.api();plan=api.build_plan(self.root,self.fresh,self.commit)
        api.apply_plan(self.root,self.fresh,plan,verify=lambda:None)
        self.write(self.root,'knowledge/guide.txt','edited again')
        self.write(self.fresh,'app/code.py','value = 5')
        upgrade_app.apply_standalone(self.root,self.fresh,'b'*40,verify=lambda:None)
        self.assertEqual((self.root/'app/code.py').read_text(),'value = 5')
        self.assertEqual((self.root/'knowledge/guide.txt').read_text(),'edited again')

    def test_source_archive_does_not_introduce_group_write_permissions(self):
        import io
        import tarfile
        archive=self.base/'source.tar'
        with tarfile.open(archive,'w') as target:
            for name, mode in [('release/a.py',0o664),('release/run.sh',0o775)]:
                entry=tarfile.TarInfo(name);entry.size=1;entry.mode=mode
                target.addfile(entry,io.BytesIO(b'x'))
        upgrade_app.extract_source(archive,self.fresh)
        self.assertEqual((self.fresh/'a.py').stat().st_mode & 0o777,0o644)
        self.assertEqual((self.fresh/'run.sh').stat().st_mode & 0o777,0o755)

    def test_cli_prints_working_retained_recovery_command(self):
        import contextlib
        import io
        import shlex
        import shutil
        import subprocess
        from types import SimpleNamespace
        from unittest.mock import patch
        api=self.api(); plan=api.build_plan(self.root,self.fresh,self.commit)
        file=self.base/'plan.json';file.write_text(json.dumps(plan))
        args=SimpleNamespace(command='apply-migration',plan=str(file),yes=True)
        out=io.StringIO()
        def stage(commit, destination):
            self.assertEqual(commit,self.commit)
            shutil.copytree(self.fresh,destination)
        with patch('app.upgrade_app.stage_source',side_effect=stage), patch('app.upgrade_app.health'), patch('upgrade_recovery.ensure_stopped'), contextlib.redirect_stdout(out):
            self.assertEqual(api.run(self.root,args),0)
        command=next(line.split('Offline rollback: ',1)[1] for line in out.getvalue().splitlines() if 'Offline rollback: ' in line)
        words=shlex.split(command)
        self.assertEqual(words[words.index('--root')+1],str(self.root))
        self.assertTrue(Path(words[1]).is_file())
        # Port probes need sockets, so exercise the same retained helper's rollback function here.
        import runpy
        recovery=runpy.run_path(words[1])
        recovery['rollback'](self.root,words[-1])
        self.assertEqual((self.root/'app/code.py').read_text(),'value = 1')

    def test_plan_rejects_wrong_root_and_preserved_file_edits(self):
        api=self.api();plan=api.build_plan(self.root,self.fresh,self.commit)
        plan['root']=str(self.base/'other')
        with self.assertRaises(ValueError):api.apply_plan(self.root,self.fresh,plan,verify=lambda:None)
        plan=api.build_plan(self.root,self.fresh,self.commit)
        self.write(self.root,'knowledge/guide.txt','changed after review')
        with self.assertRaises(ValueError):api.apply_plan(self.root,self.fresh,plan,verify=lambda:None)

    def test_invalid_metadata_is_rejected(self):
        for value in ([],{'app':None},{'app':[]}):
            with self.subTest(value=value):
                self.write(self.root,'runtime/installation.json',json.dumps(value))
                with self.assertRaises(ValueError): self.api().build_plan(self.root,self.fresh,self.commit)
        with self.assertRaises(ValueError): upgrade_app.stage_source(123,self.fresh)

    def test_failed_health_restores_source(self):
        api=self.api();plan=api.build_plan(self.root,self.fresh,self.commit)
        def fail(): raise RuntimeError('health failed')
        with self.assertRaises(RuntimeError):api.apply_plan(self.root,self.fresh,plan,verify=fail)
        self.assertEqual((self.root/'app/code.py').read_text(),'value = 1')
        self.assertFalse((self.root/'runtime/installation.json').exists())
