"""Opt-in native artifact health/adoption/transaction checks; requires network.

Run EMERGENCY_NATIVE_TOOL_TESTS=1 python -m unittest tests.test_native_tool_upgrades.
These reinstall the reviewed version to exercise activation and rollback; they do
not claim compatibility with arbitrary older distributions or indexed documents.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from app import upgrade_assets, upgrade_tools
from app.config import platform_key
from upgrade_recovery import file_mode, rollback


@unittest.skipUnless(os.environ.get('EMERGENCY_NATIVE_TOOL_TESTS') == '1',
                     'requires opt-in network downloads and native tool execution')
class NativeToolUpgradeTests(unittest.TestCase):
    def exercise(self, component):
        try:
            entry = upgrade_tools.catalog(component, platform_key())
        except ValueError:
            self.skipTest('No reviewed native artifact for '+component+'/'+platform_key())
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            cache = workspace/'cache'; cache.mkdir()
            # The real downloader checks TLS, size and SHA-256 before caching.
            artifact = upgrade_assets._download(entry, cache)
            root = workspace/'installation'; root.mkdir()
            (root/'config').mkdir()
            (root/'config/settings.local.json').write_text('{"personal": true}', encoding='utf-8')
            if component == 'document-tools':
                source = Path(upgrade_tools.__file__).resolve().parent.parent/'config/document-tools.json'
                shutil.copy2(source, root/'config/document-tools.json')
            relative = ('runtime/kiwix-tools/'+platform_key() if component == 'kiwix-tools'
                        else 'runtime/document-tools/'+entry['root'])
            target = root/relative
            if component == 'kiwix-tools':
                upgrade_assets._extract(artifact, target)
            else:
                upgrade_assets._extract(artifact, target.parent)
            content = target/entry['root'] if component == 'kiwix-tools' and entry.get('root') else target
            primary = (upgrade_assets._binary(content, 'kiwix-serve') if component == 'kiwix-tools'
                       else content/entry['binary'])
            self.assertIsNotNone(primary)
            self.assertTrue(file_mode(primary) & 0o222)
            # Force real binary replacement even when reinstalling identical bytes.
            primary.chmod(file_mode(primary) & ~0o222)
            upgrade_tools.verify_tool(root, component, content, entry)

            def cached_download(url, destination, **kwargs):
                self.assertEqual(url, entry['url'])
                self.assertEqual(kwargs['sha256'], entry['sha256'])
                self.assertEqual(kwargs['expected_size'], entry['size'])
                shutil.copy2(artifact, destination)
                return destination

            # Only transport is cached. Integrity, executable checks and transactions
            # remain real, including post-activation checks and offline rollback.
            with patch('app.prepare.download', side_effect=cached_download):
                installed = upgrade_tools.adopt_tool(root, component)
                manifest = root/'runtime/installation.json'
                manifest.write_text(json.dumps({'schema_version': 1, 'components': {component: installed}}), encoding='utf-8')
                before = {p.relative_to(root).as_posix(): (upgrade_assets._hash(p), file_mode(p))
                          for p in root.rglob('*') if p.is_file()}
                transaction = upgrade_assets.upgrade(root, {
                    'component': component, 'status': 'available',
                    'installed': installed, 'candidate': entry,
                })
            journal = json.loads((root/'runtime/upgrades'/transaction/'journal.json').read_text(encoding='utf-8'))
            transitions = [record for record in journal['files'] if Path(record['path']).name == primary.name]
            self.assertTrue(transitions, 'The transaction must activate the primary executable')
            self.assertTrue(any(record['after'] and record['after_mode'] & 0o222 for record in transitions))
            active = json.loads(manifest.read_text(encoding='utf-8'))['components'][component]
            upgrade_tools.verify_installed(root, active)
            upgrade_tools.verify_tool(root, component, root/active['path'], entry)
            rollback(root, transaction)
            after = {p.relative_to(root).as_posix(): (upgrade_assets._hash(p), file_mode(p))
                     for p in root.rglob('*') if p.is_file()
                     and not p.relative_to(root).as_posix().startswith('runtime/upgrades/')}
            self.assertEqual(after, before)
            upgrade_tools.verify_installed(root, installed)
            upgrade_tools.verify_tool(root, component, content, entry)

    def test_native_kiwix_adoption_activation_and_rollback(self):
        self.exercise('kiwix-tools')

    def test_native_pdf_adoption_activation_and_rollback(self):
        self.exercise('document-tools')
