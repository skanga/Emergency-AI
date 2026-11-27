import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import upgrade_assets
from app.config import exe


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'models').mkdir()
        (self.root/'models/old.gguf').write_bytes(b'GGUFold')
        self.payload = b'GGUFnew'
        self.record = {'component':'model','status':'available','installed':{'path':'models/old.gguf','id':'small','file':'old.gguf','sha256':hashlib.sha256(b'GGUFold').hexdigest()},'candidate':{'id':'small','file':'old.gguf','path':'models/old.gguf','url':'https://example.com/new.gguf','size':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest(),'revision':'a'*40}}

    def download(self, url, dest, **kwargs):
        Path(dest).write_bytes(self.payload)
        return dest

    def test_runtime_archive_materializes_internal_library_links(self):
        import io
        import tarfile
        archive = self.root/'runtime.tar'
        with tarfile.open(archive, 'w') as target:
            member = tarfile.TarInfo('lib/libtest.so.1'); member.size = 4
            target.addfile(member, io.BytesIO(b'test'))
            link = tarfile.TarInfo('lib/libtest.so'); link.type = tarfile.SYMTYPE
            link.linkname = 'libtest.so.1'; target.addfile(link)
        destination = self.root/'extracted'
        upgrade_assets._extract(archive, destination, materialize_links=True)
        self.assertEqual((destination/'lib/libtest.so').read_bytes(), b'test')
        self.assertFalse((destination/'lib/libtest.so').is_symlink())

    def test_compressed_link_materialization_does_not_rewind_decompressor(self):
        import gzip
        import io
        import tarfile
        archive=self.root/'links.tar.gz'
        with tarfile.open(archive,'w:gz') as target:
            entry=tarfile.TarInfo('lib/data');entry.size=1024
            target.addfile(entry,io.BytesIO(b'x'*1024))
            for number in range(4):
                link=tarfile.TarInfo('lib/link'+str(number));link.type=tarfile.SYMTYPE
                link.linkname='data';target.addfile(link)
        rewinds=[];original=gzip.GzipFile.seek
        def seek(stream,offset,whence=0):
            if whence==0 and offset<stream.tell():rewinds.append(offset)
            return original(stream,offset,whence)
        with patch.object(gzip.GzipFile,'seek',seek):
            upgrade_assets._materialize_tar(archive,self.root/'materialized.tar')
        with tarfile.open(self.root/'materialized.tar') as result:
            self.assertEqual(result.extractfile('lib/link3').read(),b'x'*1024)
        self.assertEqual(rewinds,[])

    def test_runtime_archive_rejects_escaping_and_cyclic_links(self):
        import tarfile
        for name in ('../../outside', '/etc/passwd', 'link'):
            with self.subTest(target=name):
                archive = self.root/'bad.tar'
                with tarfile.open(archive, 'w') as target:
                    link = tarfile.TarInfo('link'); link.type = tarfile.SYMTYPE
                    link.linkname = name; target.addfile(link)
                with self.assertRaises(ValueError):
                    upgrade_assets._extract(archive, self.root/'bad', materialize_links=True)

    def test_unknown_asset_blocked(self):
        self.record['status']='unknown'
        with self.assertRaisesRegex(ValueError,'available'):
            upgrade_assets.upgrade(self.root,self.record)

    def test_checksum_failure_never_mutates(self):
        self.payload=b'bad'
        with patch('app.downloads.download',side_effect=self.download):
            with self.assertRaisesRegex(ValueError,'integrity'):
                upgrade_assets.upgrade(self.root,self.record)
        self.assertEqual((self.root/'models/old.gguf').read_bytes(),b'GGUFold')

    def test_symlink_directory_blocked(self):
        (self.root/'alias').symlink_to(self.root/'models',target_is_directory=True)
        self.record['installed']['path']='alias/old.gguf'
        self.record['candidate']['path']='alias/old.gguf'
        with self.assertRaisesRegex(ValueError,'symlink|managed'):
            upgrade_assets.upgrade(self.root,self.record)

    def test_model_upgrade_and_offline_rollback(self):
        from upgrade_recovery import rollback
        with patch('app.downloads.download',side_effect=self.download), patch.object(upgrade_assets,'verify_model'):
            transaction = upgrade_assets.upgrade(self.root,self.record)
        self.assertEqual((self.root/'models/old.gguf').read_bytes(),self.payload)
        rollback(self.root,transaction)
        self.assertEqual((self.root/'models/old.gguf').read_bytes(),b'GGUFold')

    def test_failed_activation_check_restores_model(self):
        with patch('app.downloads.download',side_effect=self.download), patch.object(upgrade_assets,'verify_model',side_effect=[None,RuntimeError('load failed')]):
            with self.assertRaisesRegex(RuntimeError,'load failed'):
                upgrade_assets.upgrade(self.root,self.record)
        self.assertEqual((self.root/'models/old.gguf').read_bytes(),b'GGUFold')

    def test_zim_supersedes_only_old_archive(self):
        (self.root/'zim').mkdir()
        (self.root/'zim/c_en_nopic_2025-01.zim').write_bytes(b'old')
        (self.root/'zim/custom.zim').write_bytes(b'custom')
        self.record={'component':'kiwix-data','status':'available','installed':{'path':'zim/c_en_nopic_2025-01.zim','collection':'c_en','variant':'nopic','sha256':hashlib.sha256(b'old').hexdigest()},'candidate':{'path':'zim/c_en_nopic_2025-01.zim','destination':'zim/c_en_nopic_2026-01.zim','file':'c_en_nopic_2026-01.zim','collection':'c_en','variant':'nopic','url':'https://example.com/c_en_nopic_2026-01.zim','size':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest()}}
        with patch('app.downloads.download',side_effect=self.download), patch('app.downloads._zim_checksum_valid',return_value=True), patch.object(upgrade_assets,'verify_zim'):
            upgrade_assets.upgrade(self.root,self.record)
        self.assertFalse((self.root/'zim/c_en_nopic_2025-01.zim').exists())
        self.assertTrue((self.root/'zim/c_en_nopic_2026-01.zim').exists())
        self.assertEqual((self.root/'zim/custom.zim').read_bytes(),b'custom')

    def test_runtime_package_preserves_old_backup_and_updates_release(self):
        import io
        import tarfile
        from app.config import platform_key
        relative='runtime/llama.cpp/'+platform_key()
        folder=self.root/relative
        folder.mkdir(parents=True)
        (folder/exe('llama-server')).write_bytes(b'old engine')
        (folder/'release.json').write_text('{"tag":"b1","asset":"old.tar.gz"}')
        payload=io.BytesIO()
        with tarfile.open(fileobj=payload,mode='w:gz') as archive:
            for name in (exe('llama-server'),exe('llama-cli'),'LICENSE'):
                info=tarfile.TarInfo('package/'+name)
                info.size=3
                info.mode=0o755
                archive.addfile(info,io.BytesIO(b'new'))
        self.payload=payload.getvalue()
        record={'component':'llama','status':'available','installed':{'path':relative,'tag':'b1'},'candidate':{'path':relative,'tag':'b2','asset':'new.tar.gz','platform':platform_key(),'url':'https://example.com/new.tar.gz','size':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest()}}
        with patch('app.downloads.download',side_effect=self.download), patch('app.upgrade_assets.subprocess.run'):
            transaction=upgrade_assets.upgrade(self.root,record)
        self.assertEqual((folder/exe('llama-server')).read_bytes(),b'new')
        self.assertEqual((folder/'LICENSE').read_bytes(),b'new')
        self.assertEqual(json.loads((folder/'release.json').read_text())['tag'],'b2')
        from upgrade_recovery import rollback
        rollback(self.root,transaction)
        self.assertEqual((folder/exe('llama-server')).read_bytes(),b'old engine')

    def test_guide_only_runtime_has_no_active_model(self):
        (self.root/'models/old.gguf').unlink()
        self.assertIsNone(upgrade_assets._active_model(self.root))

    def test_python_upgrade_materializes_internal_symlink(self):
        import io
        import tarfile
        from app.config import platform_key
        relative='runtime/python/'+platform_key()
        folder=self.root/relative
        (folder/'python/bin').mkdir(parents=True)
        (folder/'python/bin/python3.12').write_bytes(b'old')
        (folder/'python/bin/python3').symlink_to('python3.12')
        if os.name=='nt':
            (folder/'python/python.exe').write_bytes(b'old')
        payload=io.BytesIO()
        with tarfile.open(fileobj=payload,mode='w:gz') as archive:
            info=tarfile.TarInfo('python/bin/python3.12');info.size=3;info.mode=0o755
            archive.addfile(info,io.BytesIO(b'new'))
            link=tarfile.TarInfo('python/bin/python3');link.type=tarfile.SYMTYPE;link.linkname='python3.12'
            archive.addfile(link)
            if os.name=='nt':
                info=tarfile.TarInfo('python/python.exe');info.size=3
                archive.addfile(info,io.BytesIO(b'new'))
        self.payload=payload.getvalue()
        record={'component':'python','status':'available','installed':{'path':relative,'asset':'cpython-3.12.1+old'},'candidate':{'path':relative,'asset':'cpython-3.12.9+new','platform':platform_key(),'url':'https://example.com/python.tar.gz','size':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest()}}
        with patch('app.downloads.download',side_effect=self.download), patch('app.upgrade_assets.subprocess.run'):
            transaction=upgrade_assets.upgrade(self.root,record)
        self.assertEqual((folder/'python/bin/python3').read_bytes(),b'new')
        self.assertFalse((folder/'python/bin/python3').is_symlink())
        from upgrade_recovery import rollback
        rollback(self.root,transaction)
        self.assertTrue((folder/'python/bin/python3').is_symlink())
        self.assertEqual(str((folder/'python/bin/python3').readlink()),'python3.12')
        self.assertEqual((folder/'python/bin/python3').read_bytes(),b'old')

    def test_python_external_link_refuses_before_download(self):
        from app.config import platform_key
        relative='runtime/python/'+platform_key()
        folder=self.root/relative;folder.mkdir(parents=True)
        (folder/'external').symlink_to(self.root/'models/old.gguf')
        record={'component':'python','status':'available','installed':{'path':relative},'candidate':{'path':relative}}
        with patch('app.downloads.download') as fetch:
            with self.assertRaises(ValueError): upgrade_assets.upgrade(self.root,record)
        fetch.assert_not_called()

    def test_python_health_checks_app_with_target_interpreter(self):
        folder=self.root/'runtime/python/test'
        (folder/'python/bin').mkdir(parents=True)
        executable=folder/('python/python.exe' if os.name=='nt' else 'python/bin/python3')
        executable.write_bytes(b'python')
        (self.root/'emergency.py').write_text('pass')
        with patch('app.upgrade_assets.subprocess.run') as run:
            upgrade_assets.verify_python(folder,{'asset':'cpython-3.12.16+20261124'},self.root)
        self.assertEqual(run.call_count,2)
        command=run.call_args.args[0]
        self.assertEqual(command[0],str(executable))
        self.assertIn('_UPGRADE_BOOTSTRAP',command[4])
        self.assertEqual(command[-1],str(self.root))

    def test_in_use_python_refuses_before_download(self):
        relative='runtime/python/test'
        folder=self.root/relative
        folder.mkdir(parents=True)
        record={'component':'python','status':'available','installed':{'path':relative},'candidate':{'path':relative}}
        executable=folder/('python/python.exe' if os.name=='nt' else 'python/bin/python3')
        with patch('app.upgrade_assets.sys.executable',str(executable)),patch('app.downloads.download') as fetch:
            with self.assertRaisesRegex(ValueError,'separate system Python'):
                upgrade_assets.upgrade(self.root,record)
        fetch.assert_not_called()

    def test_document_tool_upgrade_preserves_license_and_catalog(self):
        import io
        import tarfile
        from app.config import platform_key
        relative='runtime/document-tools/old'
        (self.root/relative).mkdir(parents=True)
        (self.root/relative/'pdftotext').write_bytes(b'old')
        (self.root/'config').mkdir()
        (self.root/'config/document-tools.json').write_text(json.dumps({'supported_platforms':{platform_key():{'version':'1','root':'old'}}}))
        payload=io.BytesIO()
        with tarfile.open(fileobj=payload,mode='w:gz') as archive:
            for name in ('bin/pdftotext','bin/pdfinfo','README','COPYING','COPYING3','doc/pdftotext.1'):
                info=tarfile.TarInfo('new/'+name);info.size=3;info.mode=0o755
                archive.addfile(info,io.BytesIO(b'new'))
        self.payload=payload.getvalue()
        record={'component':'document-tools','status':'available','installed':{'path':relative,'files':{relative+'/pdftotext':hashlib.sha256(b'old').hexdigest()}},'candidate':{'root':'new','binary':'bin/pdftotext','pdfinfo':'bin/pdfinfo','version':'2','platform':platform_key(),'url':'https://example.com/doc.tar.gz','size':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest()}}
        with patch('app.downloads.download',side_effect=self.download),patch('app.upgrade_assets.verify_document'),patch('app.upgrade_assets.subprocess.run',return_value=__import__('subprocess').CompletedProcess([],0,stdout=b'Emergency AI tool verification')):
            upgrade_assets.upgrade(self.root,record)
        self.assertEqual((self.root/'runtime/document-tools/new/COPYING').read_bytes(),b'new')
        self.assertEqual(json.loads((self.root/'config/document-tools.json').read_text())['supported_platforms'][platform_key()]['root'],'new')
        self.assertFalse((self.root/relative/'pdftotext').exists())

    def test_document_indexes_block_tool_activation(self):
        (self.root/'indexes').mkdir()
        (self.root/'indexes/collection.sqlite3').write_bytes(b'index')
        with patch('app.downloads.download') as fetch:
            with self.assertRaisesRegex(ValueError,'index migration'):
                upgrade_assets._document_changes(self.root,{'path':'runtime/document-tools/old'},{},self.root/'stage')
        fetch.assert_not_called()

    def test_runtime_uses_sibling_shared_library(self):
        import shutil
        import subprocess
        import sys
        if sys.platform!='linux' or not shutil.which('cc'):
            self.skipTest('Linux C compiler unavailable')
        folder=self.root/'engine';folder.mkdir()
        (folder/'library.c').write_text('int answer(void) {return 0;}')
        (folder/'main.c').write_text('extern int answer(void); int main(void) {return answer();}')
        subprocess.run(['cc','-shared','-fPIC',str(folder/'library.c'),'-o',str(folder/'libprobe.so')],check=True)
        subprocess.run(['cc',str(folder/'main.c'),'-L'+str(folder),'-lprobe','-o',str(folder/exe('llama-server'))],check=True)
        upgrade_assets.verify_runtime(folder)

    def test_model_check_selects_configured_cuda_runtime(self):
        from app.config import platform_key
        (self.root/'config').mkdir()
        (self.root/'config/settings.local.json').write_text('{"llm_acceleration":"cuda"}')
        folder=self.root/'runtime/llama.cpp'/(platform_key()+'-cuda');folder.mkdir(parents=True)
        (folder/exe('llama-cli')).write_bytes(b'fake')
        (folder/exe('llama-server')).write_bytes(b'fake')
        with patch('app.launcher.gpu_devices',return_value=([('CUDA0','GPU')],'')),patch('app.upgrade_assets.subprocess.run') as run:
            upgrade_assets.verify_model(self.root,self.root/'models/old.gguf')
        self.assertEqual(run.call_args.args[0][0],str(folder/exe('llama-cli')))
        self.assertIn('--n-gpu-layers',run.call_args.args[0])
        if os.name!='nt':
            variable='DYLD_LIBRARY_PATH' if sys.platform=='darwin' else 'LD_LIBRARY_PATH'
            self.assertIn(str(folder),run.call_args.kwargs['env'][variable])

    def test_zim_read_requires_managed_kiwix(self):
        with self.assertRaisesRegex(ValueError,'kiwix-serve'):
            upgrade_assets.verify_zim(self.root,self.root/'missing.zim')

    def test_zim_check_reads_main_entry_and_stops_service(self):
        from app.config import platform_key
        folder=self.root/'runtime/kiwix-tools'/platform_key();folder.mkdir(parents=True)
        (folder/exe('kiwix-serve')).write_bytes(b'fake')
        with patch('app.upgrade_assets.socket.socket') as sock,patch('app.upgrade_assets.subprocess.Popen') as spawn,patch('app.kiwix.KiwixClient.books',return_value=[{'content_url':'/content/book/'}]),patch('app.net.get_text',return_value='<html>Article body</html>') as read:
            sock.return_value.__enter__.return_value.getsockname.return_value=('127.0.0.1',12345)
            spawn.return_value.poll.return_value=None
            upgrade_assets.verify_zim(self.root,self.root/'candidate.zim')
        self.assertTrue(read.call_args.args[0].endswith('/content/book/'))
        spawn.return_value.terminate.assert_called_once()
        spawn.return_value.wait.assert_called_once()

    def test_version_scoped_policy_blocks_archive_update(self):
        (self.root/'config').mkdir()
        (self.root/'config/source-policy.json').write_text(json.dumps({'rules':[{'sources':{'kiwix:entry':'edition-uuid'}}]}))
        self.record['component']='kiwix-data'
        with patch('app.downloads.download') as download:
            with self.assertRaisesRegex(ValueError,'policy'):
                upgrade_assets.upgrade(self.root,self.record)
        download.assert_not_called()

    def test_archive_traversal_rejected_before_extract(self):
        import zipfile
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as source:
            source.writestr('../escaped','bad')
        with patch('app.downloads.extract') as extract:
            with self.assertRaisesRegex(ValueError,'path'):
                upgrade_assets._extract(archive,self.root/'staging')
        extract.assert_not_called()

    def test_pdf_collection_blocks_without_download(self):
        self.record['component']='kiwix-data'
        self.record['installed']['document_format']='nautilus'
        with patch('app.downloads.download') as download:
            with self.assertRaisesRegex(ValueError,'index'):
                upgrade_assets.upgrade(self.root,self.record)
        download.assert_not_called()


if __name__=='__main__':
    unittest.main()
