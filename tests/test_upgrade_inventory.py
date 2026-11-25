import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import upgrade_inventory


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'config').mkdir()
        (self.root/'models').mkdir()
        self.payload=b'GGUFtest'
        (self.root/'models/test.gguf').write_bytes(self.payload)
        self.model={'id':'known','file':'test.gguf','revision':'a'*40,'url':'https://huggingface.co/a/b/resolve/'+'a'*40+'/test.gguf','size_bytes':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest()}
        (self.root/'config/models.json').write_text(json.dumps({'models':[self.model]}))

    def test_verified_model_adoption_and_manifest_rollback(self):
        with patch('app.prepare.download') as download:
            result=upgrade_inventory.adopt(self.root,['model'])
        download.assert_not_called()
        self.assertEqual(result['unknown'],[])
        manifest=json.loads((self.root/'runtime/installation.json').read_text())
        self.assertEqual(manifest['components']['model']['id'],'known')
        from upgrade_recovery import rollback
        rollback(self.root,result['transaction_id'])
        self.assertFalse((self.root/'runtime/installation.json').exists())
        self.assertEqual((self.root/'models/test.gguf').read_bytes(),self.payload)

    def test_modified_model_is_not_adopted(self):
        (self.root/'models/test.gguf').write_bytes(b'changed!')
        result=upgrade_inventory.adopt(self.root,['model'])
        self.assertEqual(result['adopted'],[])
        self.assertIsNone(result['transaction_id'])
        self.assertFalse((self.root/'runtime/installation.json').exists())

    def test_symlink_model_is_not_adopted(self):
        (self.root/'models/test.gguf').unlink()
        (self.root/'external').write_bytes(self.payload)
        (self.root/'models/test.gguf').symlink_to(self.root/'external')
        result=upgrade_inventory.adopt(self.root,['model'])
        self.assertEqual(result['adopted'],[])
        self.assertIn('symlink',result['unknown'][0]['reason'])

    def zim(self):
        (self.root/'zim').mkdir()
        name='wikipedia_en_all_nopic_2025-01.zim'
        (self.root/'zim'/name).write_bytes(b'archive')
        (self.root/'config/zims.json').write_text(json.dumps({'zims':[{'name':'wikipedia_en_all','lang':'en','variant':'nopic'}]}))
        xml='<feed xmlns="http://www.w3.org/2005/Atom"><entry><link type="application/x-zim" href="https://download.kiwix.org/zim/wikipedia/'+name+'.meta4"/></entry></feed>'
        meta='<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="'+name+'"><size>7</size><hash type="sha-256">'+hashlib.sha256(b'archive').hexdigest()+'</hash></file></metalink>'
        return name,xml,meta

    def test_exact_zim_edition_adopted_without_asset_download(self):
        name,xml,meta=self.zim()
        with patch('app.upgrade_inventory._text',side_effect=lambda u,t:meta if u.endswith('.meta4') else xml), patch('app.prepare._zim_checksum_valid',return_value=True),patch('app.prepare.download') as download:
            result=upgrade_inventory.adopt(self.root,['kiwix-data'])
        download.assert_not_called()
        self.assertEqual(result['unknown'],[])
        manifest=json.loads((self.root/'runtime/installation.json').read_text())
        self.assertEqual(manifest['components']['kiwix-data'][0]['path'],'zim/'+name)

    def test_missing_old_metalink_does_not_adopt_latest(self):
        name,xml,meta=self.zim()
        with patch('app.upgrade_inventory._text',return_value=xml.replace('2025-01','2026-01')):
            result=upgrade_inventory.adopt(self.root,['kiwix-data'])
        self.assertEqual(result['adopted'],[])
        self.assertIn('exact installed edition',result['unknown'][0]['reason'])

    def test_untrusted_metalink_host_is_refused(self):
        name,xml,meta=self.zim()
        with patch('app.upgrade_inventory._text',return_value=xml.replace('download.kiwix.org','example.com')) as fetch:
            result=upgrade_inventory.adopt(self.root,['kiwix-data'])
        self.assertEqual(result['adopted'],[])
        self.assertEqual(fetch.call_count,1)

    def test_official_load_balancer_metalink_is_verified(self):
        name,xml,meta=self.zim()
        xml=xml.replace('download.kiwix.org','lb.download.kiwix.org')
        with patch('app.upgrade_inventory._text',side_effect=lambda u,t:meta if u.endswith('.meta4') else xml) as fetch, patch('app.prepare._zim_checksum_valid',return_value=True):
            result=upgrade_inventory.adopt(self.root,['kiwix-data'])
        self.assertEqual(result['unknown'],[])
        self.assertEqual(len(result['adopted']),1)
        self.assertTrue(fetch.call_args.args[0].startswith('https://lb.download.kiwix.org/'))

    def test_load_balancer_lookalike_hosts_are_refused(self):
        for host in ('lb.download.kiwix.org.example.com','lb.download.kiwix.org@evil.example'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                upgrade_inventory._official('https://'+host+'/archive.zim.meta4',
                                            ('download.kiwix.org','archive.download.kiwix.org','lb.download.kiwix.org'))

if __name__=='__main__':
    unittest.main()
