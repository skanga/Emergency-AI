"""Opt-in native Python and llama runtime transaction checks using real releases.

These reinstall the same publisher-digest-verified version in a temporary root.
Release metadata is pinned to llama b12751 / Python 20261124; these tests do not
check the newest upstream release or call the GitHub metadata API.
They do not claim historical version migration, GPU compatibility or inference:
llama is checked without a model; Python runs stdlib and application import probes.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from app import updates, upgrade_assets
from app.config import platform_key
from upgrade_recovery import file_mode, rollback


FIXTURE = Path(__file__).parent/'fixtures/native-runtime-releases.json'


def pinned_release(url, timeout):
    """Use reviewed publisher metadata; artifact transport remains real HTTPS."""
    releases = json.loads(FIXTURE.read_text(encoding='utf-8'))
    if url == 'https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10':
        return [releases['llama']]
    if url == 'https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest':
        return releases['python']
    raise AssertionError('Unexpected metadata URL: '+url)


class NativeRuntimeMetadataTests(unittest.TestCase):
    def test_pins_select_verified_artifacts_for_every_native_ci_platform(self):
        for platform in ('linux-x86_64', 'linux-arm64', 'macos-x86_64', 'macos-arm64', 'windows-x86_64'):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp, patch.object(updates, 'platform_key', return_value=platform), patch.object(updates, '_json', side_effect=AssertionError('Live metadata forbidden')):
                python = updates._tool(updates._row('python', {
                    'platform': platform, 'path': 'runtime/python/'+platform,
                    'asset': 'cpython-3.12.0+0-placeholder-install_only.tar.gz',
                }), {}, 60, root=Path(temp), fetch_json=pinned_release)
                llama = updates._llama(updates._row('llama', {
                    'platform': platform, 'path': 'runtime/llama.cpp/'+platform,
                    'tag': 'b0', 'asset': 'placeholder', 'backend': 'cpu',
                }), 60, fetch_json=pinned_release)
                for row in (python, llama):
                    self.assertEqual(row['status'], 'available', row['reason'])
                    self.assertRegex(row['candidate']['sha256'], r'^[a-f0-9]{64}$')
                    self.assertGreater(row['candidate']['size'], 0)
                self.assertEqual(llama['candidate']['tag'], 'b12751')
                self.assertIn('+20261124-', python['candidate']['asset'])


@unittest.skipUnless(os.environ.get('EMERGENCY_NATIVE_TOOL_TESTS') == '1',
                     'requires opt-in network downloads and native runtime execution')
class NativeRuntimeUpgradeTests(unittest.TestCase):
    def snapshot(self, root):
        return {path.relative_to(root).as_posix(): (upgrade_assets._hash(path), file_mode(path))
                for path in root.rglob('*') if path.is_file()
                and not path.relative_to(root).as_posix().startswith('runtime/upgrades/')}

    def exercise(self, component):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            root = workspace/'installation'; root.mkdir()
            relative = ('runtime/python/' if component == 'python' else 'runtime/llama.cpp/')+platform_key()
            target = root/relative
            baseline = {'platform': platform_key(), 'path': relative}
            if component == 'python':
                baseline['asset'] = 'cpython-3.12.0+0-placeholder-install_only.tar.gz'
                row = updates._tool(updates._row(component, baseline), {}, 60, root=root, fetch_json=pinned_release)
            else:
                baseline.update(tag='b0', asset='placeholder', backend='cpu')
                row = updates._llama(updates._row(component, baseline), 60, fetch_json=pinned_release)
            self.assertEqual(row['status'], 'available', row.get('reason'))
            candidate = row['candidate']
            self.assertEqual(candidate['platform'], platform_key())
            self.assertRegex(candidate['sha256'], r'^[a-f0-9]{64}$')
            cache = workspace/'cache'; cache.mkdir()
            artifact = upgrade_assets._download(candidate, cache)
            extracted = workspace/'extracted'
            upgrade_assets._extract(artifact, extracted, materialize_links=True)
            if component == 'python':
                self.assertTrue(candidate['asset'].startswith('cpython-3.12.'))
                content = extracted
            else:
                entries = list(extracted.iterdir())
                content = entries[0] if len(entries) == 1 and entries[0].is_dir() else extracted
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(content), str(target))
            source = Path(upgrade_assets.__file__).resolve().parent.parent
            shutil.copytree(source/'config', root/'config')
            (root/'config/settings.local.json').write_text('{"personal": true}', encoding='utf-8')
            if component == 'python':
                shutil.copytree(source/'app', root/'app', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                for name in ('emergency.py', 'upgrade_recovery.py'):
                    shutil.copy2(source/name, root/name)
            installed = dict(candidate, path=relative)
            manifest = root/'runtime/installation.json'
            manifest.write_text(json.dumps({'schema_version': 1, 'components': {component: installed}}), encoding='utf-8')

            def verify():
                if component == 'python':
                    upgrade_assets.verify_python(target, candidate, root)
                else:
                    upgrade_assets.verify_runtime(target, backend='cpu')

            primary = (target/'python'/('python.exe' if os.name == 'nt' else 'bin/python3')
                       if component == 'python' else upgrade_assets._binary(target, 'llama-server'))
            self.assertIsNotNone(primary)
            self.assertTrue(file_mode(primary) & 0o222)
            # Force real binary replacement even when reinstalling identical bytes.
            primary.chmod(file_mode(primary) & ~0o222)
            verify()
            before = self.snapshot(root)

            def cached_download(url, destination, **kwargs):
                self.assertEqual(url, candidate['url'])
                self.assertEqual(kwargs['sha256'], candidate['sha256'])
                self.assertEqual(kwargs['expected_size'], candidate['size'])
                shutil.copy2(artifact, destination)
                return destination

            # Repeated transport alone is cached. All archive handling, integrity,
            # capability checks, activation and rollback execute production code.
            with patch('app.prepare.download', side_effect=cached_download):
                transaction = upgrade_assets.upgrade(root, {
                    'component': component, 'status': 'available',
                    'installed': installed, 'candidate': candidate,
                })
            journal = json.loads((root/'runtime/upgrades'/transaction/'journal.json').read_text(encoding='utf-8'))
            transition = next(record for record in journal['files']
                              if record['path'] == primary.relative_to(root).as_posix())
            self.assertEqual(transition['before'], transition['after'])
            self.assertFalse(transition['before_mode'] & 0o222)
            self.assertTrue(transition['after_mode'] & 0o222)
            self.assertTrue(file_mode(primary) & 0o222)
            verify()
            active = json.loads(manifest.read_text(encoding='utf-8'))['components'][component]
            self.assertEqual(active['sha256'], candidate['sha256'])
            self.assertEqual(active['asset'], candidate['asset'])
            if component == 'llama':
                release = json.loads((target/'release.json').read_text(encoding='utf-8'))
                self.assertEqual(release['model_check'], 'not_run: no local model')
            rollback(root, transaction)
            self.assertEqual(self.snapshot(root), before)
            verify()

    def test_native_same_minor_python_activation_and_rollback(self):
        self.exercise('python')

    def test_native_llama_cpu_activation_and_rollback_without_model(self):
        self.exercise('llama')
