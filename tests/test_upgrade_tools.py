import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import exe, platform_key
from app.prepare import KIWIX_ASSETS


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.relative='runtime/kiwix-tools/'+platform_key()
        self.folder=self.root/self.relative/'release'
        self.folder.mkdir(parents=True)
        (self.folder/exe('kiwix-serve')).write_bytes(b'known binary')
        payload=io.BytesIO()
        with tarfile.open(fileobj=payload,mode='w:gz') as archive:
            entry=tarfile.TarInfo('release/'+exe('kiwix-serve'));entry.size=12
            archive.addfile(entry,io.BytesIO(b'known binary'))
        self.payload=payload.getvalue()
        self.entry={'version':'1.0','root':'release','asset':'release.tar.gz','url':'https://download.kiwix.org/release/kiwix-tools/release.tar.gz','size':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest(),'platform':platform_key(),'verification':'project-pinned-sha256'}

    def api(self):
        from app import upgrade_tools
        return upgrade_tools

    def download(self,url,dest,**kwargs):Path(dest).write_bytes(self.payload)

    def test_adopt_verifies_installed_tool_bytes_and_records_owned_files(self):
        api=self.api()
        with patch.object(api,'catalog',return_value=self.entry),patch.object(api,'platform_key',return_value=platform_key()),patch('app.downloads.download',side_effect=self.download),patch.object(api,'verify_tool') as health:
            record=api.adopt_tool(self.root,'kiwix-tools')
        self.assertEqual(record['path'],self.relative)
        self.assertEqual(record['verification'],'project-pinned-sha256')
        self.assertIn(self.relative+'/release/'+exe('kiwix-serve'),record['files'])
        health.assert_called_once()
        api.verify_installed(self.root,record)
        (self.folder/exe('kiwix-serve')).write_bytes(b'changed')
        with self.assertRaises(ValueError):api.verify_installed(self.root,record)

    def test_unknown_or_extra_installed_files_block_adoption(self):
        api=self.api();(self.folder/'custom').write_bytes(b'personal')
        with patch.object(api,'catalog',return_value=self.entry),patch.object(api,'platform_key',return_value=platform_key()),patch('app.downloads.download',side_effect=self.download),patch.object(api,'verify_tool') as health:
            with self.assertRaisesRegex(ValueError,'differ'):api.adopt_tool(self.root,'kiwix-tools')
        health.assert_not_called()

    def test_unsupported_platform_has_no_inferred_candidate(self):
        with self.assertRaises(ValueError):self.api().catalog('kiwix-tools','unknown')

    def test_kiwix_health_reads_each_installed_archive(self):
        api=self.api();(self.root/'zim').mkdir()
        for name in ('one.zim','two.zim'):(self.root/'zim'/name).write_bytes(b'zim')
        with patch('app.upgrade_assets.verify_runtime'),patch('app.upgrade_assets.verify_zim') as read:
            api.verify_tool(self.root,'kiwix-tools',self.folder,self.entry)
        self.assertEqual(read.call_count,2)
        self.assertEqual(read.call_args.kwargs['runtime'],self.folder)

    def test_kiwix_address_fallback_is_wsl_only(self):
        from unittest.mock import MagicMock
        from app.upgrade_assets import verify_zim
        archive=self.root/'test.zim';archive.write_bytes(b'zim')
        for wsl in (False,True):
            with self.subTest(wsl=wsl):
                calls=[]
                def spawn(command,**kwargs):
                    calls.append(command)
                    process=MagicMock()
                    if command[2]=='127.0.0.1':
                        kwargs['stderr'].write(b'ERROR: IP address is not available on this system: 127.0.0.1')
                        kwargs['stderr'].flush();process.poll.return_value=1
                    else:process.poll.return_value=None
                    return process
                with patch('app.launcher._is_wsl',return_value=wsl),patch('app.upgrade_assets._binary',return_value=self.folder/exe('kiwix-serve')),patch('app.upgrade_assets.subprocess.Popen',side_effect=spawn),patch('app.upgrade_assets.socket.socket') as socket,patch('app.kiwix.KiwixClient.books',return_value=[{'content_url':'/content/test'}]),patch('app.net.get_text',return_value='content'):
                    socket.return_value.__enter__.return_value.getsockname.return_value=('127.0.0.1',12345)
                    if wsl:verify_zim(self.root,archive)
                    else:
                        with self.assertRaises(ValueError):verify_zim(self.root,archive)
                self.assertEqual([command[2] for command in calls],['127.0.0.1','ipv4'] if wsl else ['127.0.0.1'])

    def test_xpdf_version_exit_99_requires_expected_identity(self):
        from app.upgrade_assets import verify_document
        import subprocess
        for name in ('bin/pdftotext','bin/pdfinfo','README','COPYING','COPYING3','doc/pdftotext.1'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'file')
        entry={'version':'4.06','binary':'bin/pdftotext','pdfinfo':'bin/pdfinfo'}
        def version(command,**kwargs):
            return subprocess.CompletedProcess(command,99,stdout=b'',stderr=(Path(command[0]).name+' version 4.06').encode())
        with patch('app.upgrade_assets.subprocess.run',side_effect=version):verify_document(self.root,entry)
        with patch('app.upgrade_assets.subprocess.run',return_value=subprocess.CompletedProcess([],99,stdout=b'',stderr=b'library error')):
            with self.assertRaises(ValueError):verify_document(self.root,entry)

    def test_discovery_requires_adoption_and_refuses_unreviewed_release(self):
        from app import updates
        api=self.api(); asset_prefix='kiwix-tools_'+KIWIX_ASSETS[platform_key()][0]
        self.entry['asset']=asset_prefix+'-1.0.tar.gz'
        row={'component':'kiwix-tools','installed':{'path':self.relative,'platform':platform_key()},'candidate':None}
        with patch.object(api,'catalog',return_value=self.entry),patch.object(updates,'_text',return_value='<a href="'+asset_prefix+'-1.0.tar.gz">x</a>'):
            result=updates._tool(row,{},10,self.root)
            self.assertEqual(result['status'],'unknown')
            row['installed'].update(asset=self.entry['asset'],sha256=self.entry['sha256'],files={'known':'hash'})
            self.assertEqual(updates._tool(row,{},10,self.root)['status'],'current')
        with patch.object(api,'catalog',return_value=self.entry),patch.object(updates,'_text',return_value='<a href="'+asset_prefix+'-2.0.tar.gz">x</a>'):
            self.assertEqual(updates._tool(row,{},10,self.root)['status'],'manual')

    def test_document_indexes_preserved_for_current_tool_but_gate_new_version(self):
        from app import updates
        api=self.api();(self.root/'indexes').mkdir();(self.root/'indexes/data.sqlite3').write_bytes(b'index')
        row={'component':'document-tools','installed':dict(self.entry,path=self.relative,files={'known':'hash'}),'candidate':None}
        with patch.object(api,'catalog',return_value=self.entry):
            self.assertEqual(updates._tool(row,{},10,self.root)['status'],'current')
        with patch.object(api,'catalog',return_value=dict(self.entry,version='2.0')):
            self.assertEqual(updates._tool(row,{},10,self.root)['status'],'manual')
        self.assertEqual((self.root/'indexes/data.sqlite3').read_bytes(),b'index')

    def test_tool_adoption_manifest_is_reversible(self):
        from app.upgrade_inventory import adopt
        from upgrade_recovery import rollback
        api=self.api()
        with patch.object(api,'adopt_tool',return_value=dict(self.entry,path=self.relative,files={'known':'hash'})):
            result=adopt(self.root,['kiwix-tools'])
        self.assertEqual(result['unknown'],[])
        self.assertEqual(json.loads((self.root/'runtime/installation.json').read_text())['components']['kiwix-tools']['version'],'1.0')
        rollback(self.root,result['transaction_id'])
        self.assertFalse((self.root/'runtime/installation.json').exists())

    def test_reviewed_kiwix_update_and_rollback_keep_provenance_consistent(self):
        from app import upgrade_assets
        from upgrade_recovery import rollback
        api=self.api()
        with patch.object(api,'catalog',return_value=self.entry),patch.object(api,'platform_key',return_value=platform_key()),patch('app.downloads.download',side_effect=self.download),patch.object(api,'verify_tool'):
            installed=api.adopt_tool(self.root,'kiwix-tools')
        manifest=self.root/'runtime/installation.json';manifest.write_text(json.dumps({'components':{'kiwix-tools':installed}}))
        payload=io.BytesIO()
        with tarfile.open(fileobj=payload,mode='w:gz') as archive:
            item=tarfile.TarInfo('release2/'+exe('kiwix-serve'));item.size=10
            archive.addfile(item,io.BytesIO(b'new binary'))
        self.payload=payload.getvalue()
        candidate=dict(self.entry,version='2.0',root='release2',asset='release2.tar.gz',size=len(self.payload),sha256=hashlib.sha256(self.payload).hexdigest())
        with patch('app.downloads.download',side_effect=self.download),patch.object(api,'verify_tool'),patch.object(upgrade_assets,'verify_runtime'):
            transaction=upgrade_assets.upgrade(self.root,{'component':'kiwix-tools','status':'available','installed':installed,'candidate':candidate})
        updated=json.loads(manifest.read_text())['components']['kiwix-tools']
        api.verify_installed(self.root,updated)
        self.assertEqual((self.root/self.relative/exe('kiwix-serve')).read_bytes(),b'new binary')
        rollback(self.root,transaction)
        api.verify_installed(self.root,installed)
        self.assertEqual(json.loads(manifest.read_text())['components']['kiwix-tools'],installed)
