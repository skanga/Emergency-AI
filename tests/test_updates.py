import json
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from app import updates


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'runtime').mkdir()
        (self.root / 'config').mkdir()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def test_inventory_unknown_standalone_and_custom_assets(self):
        (self.root / 'models').mkdir()
        (self.root / 'models/custom.gguf').write_bytes(b'custom')
        result = updates.inventory(self.root)
        self.assertEqual(result['components'][0]['status'], 'unknown')
        model = next(x for x in result['components'] if x['component'] == 'model')
        self.assertEqual(model['status'], 'unknown')
        self.assertEqual(model['installed']['path'], 'models/custom.gguf')
        json.dumps(result)

    def test_llama_selection_shares_one_request_and_skips_other_providers(self):
        for backend in ('cpu', 'cuda', 'vulkan'):
            suffix = '' if backend == 'cpu' else '-' + backend
            self.write('runtime/llama.cpp/linux-x86_64'+suffix+'/release.json', {'tag':'b1','asset':'old'})
        with patch.object(updates, '_json', return_value=[]) as fetch, patch.object(updates,'platform_key',return_value='linux-x86_64'):
            result = updates.check(self.root, components=['llama'])
        self.assertEqual(fetch.call_count, 1)
        self.assertTrue(all(r['component']=='llama' for r in result['components']))

    def test_rate_limit_reports_http_status_and_reset_without_duplicate_retries(self):
        for suffix in ('','-vulkan'):
            self.write('runtime/llama.cpp/linux-x86_64'+suffix+'/release.json', {'tag':'b1','asset':'old'})
        error = urllib.error.HTTPError('https://api.github.com/repos/ggml-org/llama.cpp/releases',403,'Forbidden',
                                      {'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'1795639092'},None)
        with patch.object(updates,'_json',side_effect=error) as fetch, patch.object(updates,'platform_key',return_value='linux-x86_64'):
            result=updates.check(self.root, components=['llama'])
        self.assertEqual(fetch.call_count,1)
        for row in result['components']:
            self.assertEqual(row['http_status'],403)
            self.assertEqual(row['retry_at'],1795639092)
            self.assertIn('rate limit',row['reason'])
            self.assertIsNone(row['candidate'])

    def test_selected_catalog_component_keeps_app_dependency(self):
        with patch.object(updates, '_json', return_value={'sha':'a' * 40}) as fetch:
            result = updates.check(self.root, components=['model'])
        self.assertEqual([r['component'] for r in result['components']], ['app', 'model'])
        self.assertEqual(fetch.call_count, 1)

    def test_rate_limit_with_invalid_reset_still_explains_failure(self):
        error = urllib.error.HTTPError('https://api.github.com/example', 429, 'Too Many Requests',
                                      {'X-RateLimit-Reset':'invalid'}, None)
        with patch.object(updates, '_json', side_effect=error):
            row = updates.check(self.root, components=['app'])['components'][0]
        self.assertEqual(row['http_status'], 429)
        self.assertIn('rate limit', row['reason'])
        self.assertNotIn('retry_at', row)

    def test_standalone_candidate_is_immutable_but_unknown_baseline_blocked(self):
        with patch.object(updates, '_json', return_value={'sha': 'a' * 40}):
            app = updates.check(self.root)['components'][0]
        self.assertEqual(app['status'], 'blocked')
        self.assertEqual(app['candidate']['commit'], 'a' * 40)
        self.assertIn('a' * 40, app['candidate']['url'])

    def test_offline_is_unavailable_not_current(self):
        with patch.object(updates, '_json', side_effect=OSError('offline')):
            app = updates.check(self.root)['components'][0]
        self.assertEqual(app['status'], 'unavailable')

    def test_deadline_returns_without_waiting_for_worker(self):
        def slow(*args, **kwargs):
            time.sleep(.3)
            return {'sha': 'a' * 40}
        start = time.monotonic()
        with patch.object(updates, '_json', side_effect=slow):
            result = updates.check(self.root, timeout=.02)
        self.assertLess(time.monotonic() - start, .2)
        self.assertEqual(result['components'][0]['status'], 'unavailable')

    def test_deadline_also_bounds_local_inventory(self):
        original = updates.inventory
        def slow(root):
            time.sleep(.3)
            return original(root)
        start = time.monotonic()
        with patch.object(updates, 'inventory', side_effect=slow):
            result = updates.check(self.root, timeout=.02)
        self.assertLess(time.monotonic()-start,.2)
        self.assertEqual(result['components'][0]['status'],'unavailable')

    def test_model_same_id_pinned_catalog_only(self):
        self.write('runtime/installation.json', {'app': {'commit': 'b'*40}, 'components': {'model': {'id':'small', 'revision':'old', 'sha256':'b'*64, 'path':'models/a.gguf', 'file':'a.gguf'}}})
        (self.root / 'models').mkdir()
        (self.root / 'models/a.gguf').write_bytes(b'old')
        model = {'id':'small', 'file':'a.gguf', 'revision':'c'*40, 'sha256':'a'*64, 'size_bytes':4, 'url':'https://huggingface.co/x/y/resolve/'+'c'*40+'/a.gguf'}
        def metadata(url, timeout):
            return {'models':[model]} if url.endswith('models.json') else {'sha':'a'*40}
        with patch.object(updates, '_json', side_effect=metadata):
            result = updates.check(self.root)
        row = next(x for x in result['components'] if x['component']=='model')
        self.assertEqual(row['status'], 'available')
        self.assertEqual(row['candidate']['id'], 'small')
        self.assertEqual(row['candidate']['size'], 4)

    def test_llama_missing_digest_is_manual(self):
        self.write('runtime/llama.cpp/linux-x86_64/release.json', {'tag':'b1','asset':'llama-b1-bin-ubuntu-x64.tar.gz'})
        data = [{'tag_name':'b2','assets':[{'name':'llama-b2-bin-ubuntu-x64.tar.gz','browser_download_url':'https://github.com/ggml-org/llama.cpp/releases/download/b2/llama-b2-bin-ubuntu-x64.tar.gz','size':123}]}]
        with patch.object(updates, '_json', side_effect=lambda u,t: data if '/releases?' in u else {'sha':'a'*40}):
            rows = updates.check(self.root)['components']
        row = next(x for x in rows if x['component']=='llama')
        self.assertEqual(row['status'],'manual')

    def test_numbered_llama_prereleases_follow_installed_build_stream(self):
        row = {'component': 'llama', 'installed': {'tag': 'b12719', 'asset': 'old', 'platform': 'linux-x86_64', 'backend': 'cpu', 'path': 'runtime/llama.cpp/linux-x86_64'}}
        asset = {'name': 'llama-b12728-bin-ubuntu-x64.tar.gz', 'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b12728/cpu.tar.gz', 'size': 123, 'digest': 'sha256:' + 'a'*64}
        releases = [{'tag_name': 'experimental', 'prerelease': True, 'assets': [asset]},
                    {'tag_name': 'b12729', 'draft': True, 'assets': [asset]},
                    {'tag_name': 'b12728', 'prerelease': True, 'assets': [asset]}]
        with patch.object(updates, '_json', return_value=releases), patch.object(updates, 'platform_key', return_value='linux-x86_64'):
            result = updates._llama(row, 10)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['candidate']['tag'], 'b12728')
        self.assertTrue(result['candidate']['prerelease'])
        self.assertIn('prerelease', result['reason'])

    def test_null_runtime_digest_is_manual_not_provider_failure(self):
        row = {'component': 'llama', 'installed': {'tag': 'b1', 'asset': 'old', 'platform': 'linux-x86_64', 'path': 'runtime/llama.cpp/linux-x86_64'}}
        release = {'tag_name': 'b2', 'assets': [{'name': 'llama-b2-bin-ubuntu-x64.tar.gz', 'browser_download_url': 'https://example.org/a.tar.gz', 'size': 123, 'digest': None}]}
        with patch.object(updates, '_json', return_value=[release]), patch.object(updates, 'platform_key', return_value='linux-x86_64'):
            self.assertEqual(updates._llama(row, 10)['status'], 'manual')

    def test_catalog_model_is_recognized_without_claiming_verified_bytes(self):
        self.write('config/models.json', {'models': [{'id': 'small', 'file': 'known.gguf'}]})
        (self.root/'models').mkdir()
        (self.root/'models/known.gguf').write_bytes(b'not verified')
        row = next(r for r in updates.inventory(self.root)['components'] if r['component']=='model')
        result = updates._model(row, {}, 10)
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['candidate'])
        self.assertIn('--adopt --component model', result['reason'])

    def test_fixed_archive_is_identified_without_claiming_current_content(self):
        self.write('config/zims.json', {'archives': [{'id': 'wikem', 'snapshot': '2020-06', 'url': 'https://archive.org/wikem_en_all_maxi_2020-06.zim'}]})
        (self.root/'zim').mkdir()
        (self.root/'zim/wikem_en_all_maxi_2020-06.zim').write_bytes(b'not verified')
        row = next(r for r in updates.inventory(self.root)['components'] if r['component']=='kiwix-data')
        result = updates._zim(self.root, row, 10)
        self.assertEqual(result['status'], 'manual')
        self.assertIn('2020-06', result['reason'])
        self.assertIsNone(result['candidate'])

    def test_zim_exact_variant_and_metalink(self):
        self.write('runtime/installation.json', {'components': {'kiwix-data': [{'collection':'wikipedia_en_all','variant':'nopic','path':'zim/wikipedia_en_all_nopic_2025-01.zim','sha256':'b'*64}]}})
        (self.root / 'zim').mkdir()
        (self.root / 'zim/wikipedia_en_all_nopic_2025-01.zim').write_bytes(b'old')
        xml = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><link type="application/x-zim" href="https://download.kiwix.org/zim/wikipedia_en_all_nopic_2026-01.zim.meta4"/><link type="application/x-zim" href="https://download.kiwix.org/zim/wikipedia_en_all_maxi_2026-02.zim.meta4"/></entry></feed>'
        metalink = '<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="wikipedia_en_all_nopic_2026-01.zim"><size>42</size><hash type="sha-256">'+'a'*64+'</hash></file></metalink>'
        with patch.object(updates, '_json', return_value={'sha':'a'*40}), patch.object(updates, '_text', side_effect=lambda u,t: metalink if u.endswith('.meta4') else xml):
            rows = updates.check(self.root)['components']
        row = next(r for r in rows if r['component']=='kiwix-data')
        self.assertEqual(row['status'], 'manual')
        self.assertIn('kiwix-serve',row['reason'])
        self.assertEqual(row['candidate']['size'],42)
        self.assertEqual(row['candidate']['file'],'wikipedia_en_all_nopic_2026-01.zim')

    def test_same_zim_filename_changed_hash_is_unknown(self):
        row={'component':'kiwix-data','installed':{'collection':'c_en','variant':'nopic','file':'c_en_nopic_2025-01.zim','path':'zim/c_en_nopic_2025-01.zim','sha256':'b'*64},'candidate':None}
        xml='<feed xmlns="http://www.w3.org/2005/Atom"><entry><link type="application/x-zim" href="https://download.kiwix.org/zim/c_en_nopic_2025-01.zim.meta4"/></entry></feed>'
        meta='<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="c_en_nopic_2025-01.zim"><size>42</size><hash type="sha-256">'+'a'*64+'</hash></file></metalink>'
        with patch.object(updates,'_text',side_effect=lambda u,t:meta if u.endswith('.meta4') else xml):
            result=updates._zim(self.root,row,30)
        self.assertEqual(result['status'],'unknown')

    def test_pinned_document_tool_candidate_is_reported(self):
        self.write('runtime/installation.json', {'components':{'document-tools':{'version':'4.05','platform':'linux-x86_64','path':'runtime/document-tools/linux-x86_64'}}})
        def fetch(url, timeout):
            if url.endswith('document-tools.json'):
                return {'supported_platforms':{'linux-x86_64':{'version':'4.06','url':'https://dl.xpdfreader.com/xpdf-4.06.tar.gz','size':42,'sha256':'a'*64}}}
            return {'sha':'b'*40}
        with patch.object(updates,'_json',side_effect=fetch):
            row=next(r for r in updates.check(self.root)['components'] if r['component']=='document-tools')
        self.assertEqual(row['candidate']['identity'],'4.06')
        self.assertEqual(row['status'],'manual')

    def test_python_candidate_matches_exact_triple(self):
        self.write('runtime/python/linux-x86_64/installation.json', {'complete':True,'asset':'cpython-3.12.1+20240101-x86_64-unknown-linux-gnu-install_only.tar.gz'})
        asset='cpython-3.12.9+20260101-x86_64-unknown-linux-gnu-install_only.tar.gz'
        with patch.object(updates,'_json',side_effect=lambda u,t: {'assets':[{'name':asset,'browser_download_url':'https://github.com/astral-sh/python-build-standalone/releases/download/20260101/'+asset,'size':42,'digest':'sha256:'+'a'*64}]} if 'python-build-standalone' in u else {'sha':'b'*40}):
            row=next(r for r in updates.check(self.root)['components'] if r['component']=='python')
        self.assertEqual(row['candidate']['asset'],asset)
        self.assertEqual(row['candidate']['sha256'],'a'*64)
        self.assertEqual(row['status'],'available')

    def test_foreign_platform_tool_is_manual_without_metadata(self):
        row={'component':'python','installed':{'platform':'foreign-platform','asset':'known'},'candidate':None}
        with patch.object(updates,'_json') as metadata:
            result=updates._tool(row,{},30,self.root)
        self.assertEqual(result['status'],'manual')
        self.assertIn('Foreign platform',result['reason'])
        metadata.assert_not_called()

    def test_zim_discovery_flags_index_and_policy_migration(self):
        (self.root/'config/zims.json').write_text(json.dumps({'zims':[{'name':'c_en','document_format':'nautilus'}]}))
        xml='<feed xmlns="http://www.w3.org/2005/Atom"><entry><link type="application/x-zim" href="https://download.kiwix.org/zim/c_en_nopic_2026-01.zim.meta4"/></entry></feed>'
        meta='<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="c_en_nopic_2026-01.zim"><size>42</size><hash type="sha-256">'+'a'*64+'</hash></file></metalink>'
        def row():
            return {'component':'kiwix-data','installed':{'collection':'c_en','variant':'nopic','file':'c_en_nopic_2025-01.zim','path':'zim/c_en_nopic_2025-01.zim','sha256':'b'*64},'candidate':None}
        with patch.object(updates,'_text',side_effect=lambda u,t:meta if u.endswith('.meta4') else xml):
            result=updates._zim(self.root,row(),30)
            self.assertEqual(result['status'],'manual')
            self.assertIn('index',result['reason'])
            self.assertIsNotNone(result['candidate'])
            (self.root/'config/zims.json').write_text('{}')
            (self.root/'config/source-policy.json').write_text('{"rules":[{"sources":{"x":"version"}}]}')
            result=updates._zim(self.root,row(),30)
            self.assertEqual(result['status'],'manual')
            self.assertIn('policy',result['reason'])

    def test_git_upstream_branch_and_dirty_status(self):
        (self.root / '.git').mkdir()
        def git(root, *args):
            return {('symbolic-ref','--short','HEAD'):'work', ('config','branch.work.remote'):'upstream', ('config','branch.work.merge'):'refs/heads/stable', ('remote','get-url','upstream'):'https://github.com/example/project.git', ('rev-parse','HEAD'):'b'*40, ('status','--porcelain'):' M app/file.py'}.get(args,'')
        with patch.object(updates, '_git', side_effect=git), patch.object(updates, '_json', return_value={'sha':'a'*40}) as fetch:
            row = updates.check(self.root)['components'][0]
        self.assertEqual(row['status'],'blocked')
        self.assertEqual(row['candidate']['repository'],'example/project')
        self.assertEqual(row['candidate']['branch'],'stable')
        self.assertIn('/commits/stable',fetch.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
