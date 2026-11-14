"""Portable backend selection, device probing and startup fallback."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import launcher, prepare


class AccelerationTests(unittest.TestCase):
    def test_vulkan_packages_for_supported_platforms(self):
        for plat, suffix in [('windows-x86_64', 'win-vulkan-x64.zip'),
                             ('windows-arm64', 'win-vulkan-arm64.zip'),
                             ('linux-x86_64', 'ubuntu-vulkan-x64.tar.gz'),
                             ('linux-arm64', 'ubuntu-vulkan-arm64.tar.gz')]:
            asset = ('llama-b123-bin-' + suffix, 'url', 100)
            self.assertEqual(prepare._llama_pick(plat, [asset], 'vulkan'), asset)

    def test_preparation_installs_cpu_and_vulkan_separately(self):
        assets = [{'name': 'llama-b123-bin-win-%s-x64.zip' % backend,
                   'browser_download_url': backend, 'size': 1} for backend in ('cpu', 'vulkan')]
        with tempfile.TemporaryDirectory() as root:
            def download(url, path, **kwargs):
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_bytes(b'x')
            def extract(path, dest):
                Path(dest).mkdir(parents=True)
                (Path(dest) / 'llama-server.exe').write_text(Path(path).name)
            with patch.object(prepare, 'RUNTIME_DIR', root), \
                    patch.object(prepare, 'get_json', return_value=[{'tag_name': 'b123', 'assets': assets}]), \
                    patch.object(prepare, 'download', side_effect=download), \
                    patch.object(prepare, 'extract', side_effect=extract), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(prepare.get_llama('windows-x86_64', prepare.T['en']))
            cpu = Path(root) / 'llama.cpp/windows-x86_64/llama-server.exe'
            gpu = Path(root) / 'llama.cpp/windows-x86_64-vulkan/llama-server.exe'
            self.assertIn('cpu', cpu.read_text())
            self.assertIn('vulkan', gpu.read_text())

    def test_probe_uses_reported_devices_not_driver_messages(self):
        result = Mock(returncode=0, stdout='Available devices:\n  Vulkan0: AMD Radeon (8192 MiB, 7000 MiB free)\n',
                      stderr='ggml_vulkan: Found 1 Vulkan devices\n')
        with patch.object(launcher.subprocess, 'run', return_value=result):
            self.assertEqual(launcher.gpu_devices('engine', 'vulkan'),
                             [('Vulkan0', 'AMD Radeon (8192 MiB, 7000 MiB free)')])
            result.returncode = 1
            self.assertEqual(launcher.gpu_devices('engine', 'vulkan'), [])

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for target, value in [('port_in_use', False), ('find_model', '/models/test.gguf'),
                              ('platform_key', 'windows-x86_64')]:
            self.stack.enter_context(patch.object(launcher, target, return_value=value))
        self.stack.enter_context(patch.object(launcher, '_ensure_exec'))
        self.find = self.stack.enter_context(patch.object(launcher, 'find_llama_server',
            side_effect=lambda backend=None: (None, None) if backend == 'cuda' else
            ('gpu' if backend == 'vulkan' else 'cpu', 'llama.cpp')))
        self.spawn = self.stack.enter_context(patch.object(launcher, '_spawn'))
        self.spawn.return_value.poll.return_value = None

    def test_auto_uses_vulkan_and_waits_for_health(self):
        engine = launcher.Launcher({}, say=lambda *_: None)
        with patch.object(launcher, 'gpu_devices', return_value=[('Vulkan0', 'GPU')]), \
                patch.object(launcher, 'get_json', return_value={'status': 'ok'}):
            self.assertTrue(engine.start_llm())
        command = self.spawn.call_args.args[0]
        self.assertEqual(command[0], 'gpu')
        self.assertIn('Vulkan0', command)
        self.assertEqual(engine.llm_acceleration, 'vulkan')

    def test_failed_gpu_retries_cpu_after_stopping_gpu(self):
        engine = launcher.Launcher({}, say=lambda *_: None)
        gpu, cpu = Mock(), Mock()
        gpu.poll.return_value = 1
        self.spawn.side_effect = [gpu, cpu]
        with patch.object(launcher, 'gpu_devices', return_value=[('Vulkan0', 'GPU')]):
            self.assertTrue(engine.start_llm())
        gpu.wait.assert_called_once()
        command = self.spawn.call_args.args[0]
        self.assertEqual(command[0], 'cpu')
        self.assertEqual(command[command.index('--device') + 1], 'none')
        self.assertEqual(engine.llm_acceleration, 'cpu')
        self.assertEqual(engine.procs, [cpu])

    def test_cpu_override_skips_gpu_probe(self):
        engine = launcher.Launcher({'llm_acceleration': 'cpu'}, say=lambda *_: None)
        with patch.object(launcher, 'gpu_devices') as probe:
            self.assertTrue(engine.start_llm())
        probe.assert_not_called()
        self.assertIn('none', self.spawn.call_args.args[0])

    def test_no_devices_uses_cpu(self):
        engine = launcher.Launcher({}, say=lambda *_: None)
        with patch.object(launcher, 'gpu_devices', return_value=[]):
            self.assertTrue(engine.start_llm())
        self.assertEqual(self.spawn.call_args.args[0][0], 'cpu')

    def test_macos_uses_metal(self):
        engine = launcher.Launcher({}, say=lambda *_: None)
        with patch.object(launcher, 'platform_key', return_value='macos-arm64'), \
                patch.object(launcher, 'gpu_devices', return_value=[('Metal', 'Apple M1')]), \
                patch.object(launcher, 'get_json', return_value={'status': 'ok'}):
            self.assertTrue(engine.start_llm())
        self.assertEqual(engine.llm_acceleration, 'metal')
        self.assertIn('Metal', self.spawn.call_args.args[0])

    def test_probe_failure_is_cpu_fallback(self):
        for failure in (OSError('missing driver'), launcher.subprocess.TimeoutExpired('engine', 15)):
            with self.subTest(failure=failure), patch.object(launcher.subprocess, 'run', side_effect=failure):
                self.assertEqual(launcher.gpu_devices('engine', 'vulkan'), [])

    def test_probe_recognizes_current_metal_device_ids(self):
        result = Mock(returncode=0, stdout='Available devices:\n  MTL0: Apple M4 (32768 MiB, 24000 MiB free)\n', stderr='')
        with patch.object(launcher.subprocess, 'run', return_value=result):
            self.assertEqual(launcher.gpu_devices('engine', 'metal')[0][0], 'MTL0')

    def test_gpu_spawn_failure_falls_back(self):
        self.spawn.side_effect = [OSError('missing library'), Mock()]
        engine = launcher.Launcher({}, say=lambda *_: None)
        with patch.object(launcher, 'gpu_devices', return_value=[('Vulkan0', 'GPU')]):
            self.assertTrue(engine.start_llm())
        self.assertEqual(engine.llm_acceleration, 'cpu')
        self.assertEqual(len(engine.procs), 1)

    def test_gpu_health_wait_and_timeout(self):
        engine = launcher.Launcher({}, say=lambda *_: None)
        engine.llm_process = process = Mock()
        process.poll.return_value = None
        with patch.object(launcher, 'get_json', side_effect=[OSError('loading'), {'status': 'ok'}]), \
                patch.object(launcher.time, 'sleep'):
            self.assertTrue(engine._gpu_ready(process, 8091))
        with patch.object(launcher.time, 'monotonic', side_effect=[0, 301]):
            self.assertFalse(engine._gpu_ready(process, 8091))

    def test_cancelled_loading_does_not_start_cpu(self):
        engine = launcher.Launcher({}, say=lambda *_: None)
        def cancelled(*args):
            engine.stop_llm()
            return False
        with patch.object(launcher, 'gpu_devices', return_value=[('Vulkan0', 'GPU')]), \
                patch.object(engine, '_gpu_ready', side_effect=cancelled):
            self.assertFalse(engine.start_llm())
        self.assertEqual(self.spawn.call_count, 1)
        self.assertEqual(engine.procs, [])

    def test_invalid_setting_does_not_spawn(self):
        engine = launcher.Launcher({'llm_acceleration': 'typo'}, say=lambda *_: None)
        self.assertFalse(engine.start_llm())
        self.spawn.assert_not_called()

    def test_interrupted_gpu_loading_stops_owned_process(self):
        engine = launcher.Launcher({}, say=lambda *_: None)
        with patch.object(launcher, 'gpu_devices', return_value=[('Vulkan0', 'GPU')]), \
                patch.object(engine, '_gpu_ready', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                engine.start_llm()
        self.assertEqual(engine.procs, [])
        self.assertIsNone(engine.llm_process)
