import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import launcher


class GpuProbeTests(unittest.TestCase):
    def setUp(self):
        self.logs = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(launcher, 'LOG_DIR', str(self.logs)))
        self.enterContext(patch.object(launcher, '_ensure_exec'))
        self.enterContext(patch.object(launcher, '_wsl_driver_dir', return_value='/usr/lib/wsl/drivers/active'))
        self.enterContext(patch.object(launcher, '_is_wsl', return_value=True))
        self.enterContext(patch.object(launcher.sys, 'platform', 'linux'))
        self.enterContext(patch.object(launcher, 'is_windows', return_value=False))
        self.run = self.enterContext(patch.object(launcher.subprocess, 'run'))
        self.run.return_value = subprocess.CompletedProcess([], 0, 'Available devices:\n  CUDA0: Test GPU (8192 MiB)\n', '')

    def test_success_returns_devices_and_records_probe_without_environment_secrets(self):
        with patch.dict(launcher.os.environ, {'UNRELATED_SECRET': 'do-not-log-this'}):
            devices, reason = launcher.gpu_devices('/kit/llama-server', 'cuda')
        self.assertEqual(devices, [('CUDA0', 'Test GPU (8192 MiB)')])
        self.assertEqual(reason, '')
        log = (self.logs / 'gpu-probe.log').read_text()
        for text in ['/kit/llama-server', '/usr/lib/wsl/drivers/active', 'CUDA0', 'return code: 0']:
            self.assertIn(text, log)
        self.assertNotIn('do-not-log-this', log)

    def test_crash_explains_signal_and_retains_stderr(self):
        self.run.return_value = subprocess.CompletedProcess([], -signal.SIGSEGV, '', 'compiler failed')
        devices, reason = launcher.gpu_devices('/kit/llama-server', 'cuda')
        self.assertEqual(devices, [])
        self.assertIn('SIGSEGV', reason)
        self.assertIn('compiler failed', (self.logs / 'gpu-probe.log').read_text())

    def test_no_devices_is_distinguished_from_crash(self):
        self.run.return_value = subprocess.CompletedProcess([], 0, 'Available devices:\n  (none)\n', 'driver unavailable')
        devices, reason = launcher.gpu_devices('/kit/llama-server', 'cuda')
        self.assertEqual(devices, [])
        self.assertIn('no usable devices', reason)
        self.assertIn('driver unavailable', (self.logs / 'gpu-probe.log').read_text())

    def test_missing_executable_and_timeout_return_diagnostics(self):
        for error, expected in [(FileNotFoundError('missing binary'), 'missing binary'),
                                (subprocess.TimeoutExpired('probe', 15, stderr=b'partial output'), 'timed out')]:
            with self.subTest(error=type(error).__name__):
                self.run.side_effect = error
                devices, reason = launcher.gpu_devices('/kit/llama-server', 'cuda')
                self.assertEqual(devices, [])
                self.assertIn(expected, reason)
        self.assertIn('partial output', (self.logs / 'gpu-probe.log').read_text())

    def test_nonzero_exit_preserves_loader_error(self):
        self.run.return_value = subprocess.CompletedProcess([], 127, '', 'libcudart.so.13: cannot open shared object file')
        devices, reason = launcher.gpu_devices('/kit/llama-server', 'cuda')
        self.assertEqual(devices, [])
        self.assertIn('127', reason)
        self.assertIn('libcudart.so.13', (self.logs / 'gpu-probe.log').read_text())

    def test_unwritable_diagnostic_log_does_not_break_probe(self):
        with patch('builtins.open', side_effect=PermissionError('read only')):
            devices, reason = launcher.gpu_devices('/kit/llama-server', 'cuda')
        self.assertTrue(devices)
        self.assertEqual(reason, '')

    def test_probe_and_spawn_use_same_cuda_library_precedence(self):
        launcher.gpu_devices('/kit/llama-server', 'cuda')
        with patch.object(launcher.subprocess, 'Popen') as popen:
            launcher._spawn(['/kit/llama-server', '-m', 'model.gguf'], 'llm.log', backend='cuda')
        self.assertEqual(self.run.call_args.kwargs['env'], popen.call_args.kwargs['env'])
        self.assertTrue(popen.call_args.kwargs['env']['LD_LIBRARY_PATH'].startswith(os.pathsep.join(['/usr/lib/wsl/drivers/active', '/kit'])))


class BackendSelectionTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.app = launcher.Launcher({}, say=self.messages.append)
        self.enterContext(patch.object(launcher, 'port_in_use', return_value=False))
        self.enterContext(patch.object(launcher, 'platform_key', return_value='linux-x86_64'))
        self.enterContext(patch.object(launcher, 'find_model', return_value='/kit/model.gguf'))
        self.enterContext(patch.object(launcher, 'find_llama_server',
                                side_effect=lambda backend=None: (f'/kit/{backend or "cpu"}/llama-server', 'llama.cpp')))
        self.enterContext(patch.object(launcher, '_ensure_exec'))
        self.enterContext(patch('app.generation.generation_options', return_value={'context': 8192}))
        self.probe = self.enterContext(patch.object(launcher, 'gpu_devices'))
        self.spawn = self.enterContext(patch.object(launcher, '_spawn', return_value=Mock()))
        self.enterContext(patch.object(self.app, '_gpu_ready', return_value=True))

    def test_cuda_success_passes_backend_and_device_to_spawn(self):
        self.probe.return_value = ([('CUDA0', 'Test GPU')], '')
        self.assertTrue(self.app.start_llm())
        self.assertEqual(self.app.llm_acceleration, 'cuda')
        self.assertEqual(self.spawn.call_args.kwargs['backend'], 'cuda')
        command = self.spawn.call_args.args[0]
        self.assertEqual(command[command.index('--device') + 1], 'CUDA0')

    def test_crash_then_no_vulkan_device_falls_back_to_cpu(self):
        self.probe.side_effect = [([], 'probe crashed (SIGSEGV)'), ([], 'no usable devices')]
        self.assertTrue(self.app.start_llm())
        self.assertEqual(self.app.llm_acceleration, 'cpu')
        self.assertIn('SIGSEGV', '\n'.join(self.messages))
        self.assertIn('gpu-probe.log', '\n'.join(self.messages))
        command = self.spawn.call_args.args[0]
        self.assertEqual(command[command.index('--n-gpu-layers') + 1], '0')

    def test_explicit_cpu_does_not_probe_gpu(self):
        self.app.settings['llm_acceleration'] = 'cpu'
        self.assertTrue(self.app.start_llm())
        self.probe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
