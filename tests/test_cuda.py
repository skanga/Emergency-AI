"""Optional CUDA packaging and CUDA -> Vulkan -> CPU selection."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import launcher, prepare


class CudaTests(unittest.TestCase):
    def test_selects_matching_engine_and_runtime_from_same_release(self):
        for plat, suffix, prefix in [
                ('windows-x86_64', 'win-cuda-13.5-x64.zip', 'cudart-llama-bin-'),
                ('linux-arm64', 'ubuntu-cuda-13.5-arm64.tar.gz', 'cudart-llama-b123-bin-')]:
            engine = ('llama-b123-bin-' + suffix, 'engine', 10)
            runtime = (prefix + suffix, 'runtime', 20)
            self.assertEqual(prepare._cuda_pick(plat, [runtime, engine]), (engine, runtime))
            self.assertIsNone(prepare._cuda_pick(plat, [engine]))
            wrong_version = (runtime[0].replace('13.5', '12.8'), 'wrong', 20)
            self.assertIsNone(prepare._cuda_pick(plat, [engine, wrong_version]))

    def test_install_bundles_runtime_next_to_executable_and_is_reusable(self):
        with tempfile.TemporaryDirectory() as root:
            engine = ('llama-b123-bin-win-cuda-13.5-x64.zip', 'engine', 1)
            runtime = ('cudart-llama-bin-win-cuda-13.5-x64.zip', 'runtime', 1)
            def download(url, dest, **kwargs):
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                Path(dest).write_bytes(b'x')
            def extract(archive, dest):
                folder = Path(dest) / ('lib' if 'cudart' in archive else 'bin')
                folder.mkdir(parents=True, exist_ok=True)
                (folder / ('cudart64_13.dll' if 'cudart' in archive else 'llama-server.exe')).write_bytes(b'x')
            with patch.object(prepare, 'RUNTIME_DIR', root), \
                    patch.object(prepare, 'download', side_effect=download) as fetch, \
                    patch.object(prepare, 'extract', side_effect=extract), \
                    contextlib.redirect_stdout(io.StringIO()):
                for _ in range(2):
                    self.assertTrue(prepare._install_llama('windows-x86_64', prepare.T['en'], 'b123',
                                                         engine, 'cuda', runtime))
                self.assertEqual(fetch.call_count, 2)
                (Path(root) / 'llama.cpp/windows-x86_64-cuda/bin/cudart64_13.dll').unlink()
                self.assertTrue(prepare._install_llama('windows-x86_64', prepare.T['en'], 'b123',
                                                     engine, 'cuda', runtime))
                self.assertEqual(fetch.call_count, 4)
            self.assertTrue((Path(root) / 'llama.cpp/windows-x86_64-cuda/bin/cudart64_13.dll').exists())

    def test_cuda_probe_reports_cuda_devices(self):
        with patch.object(launcher.subprocess, 'run', return_value=Mock(returncode=0,
                stdout='Available devices:\n  CUDA0: NVIDIA GPU (8192 MiB, 7000 MiB free)\n', stderr='')):
            self.assertEqual(launcher.gpu_devices('engine', 'cuda')[0][0], 'CUDA0')

    def test_cuda_failure_tries_vulkan_before_cpu(self):
        for success, expected in [('cuda', ['cuda']), ('vulkan', ['cuda', 'vulkan']),
                                  ('none', ['cuda', 'vulkan', 'cpu'])]:
            with self.subTest(success=success), contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(launcher, 'port_in_use', return_value=False))
                stack.enter_context(patch.object(launcher, 'platform_key', return_value='windows-x86_64'))
                stack.enter_context(patch.object(launcher, '_ensure_exec'))
                stack.enter_context(patch.object(launcher, 'find_model', return_value='model.gguf'))
                stack.enter_context(patch.object(launcher, 'find_llama_server',
                                                side_effect=lambda backend=None: (backend or 'cpu', 'llama.cpp')))
                stack.enter_context(patch.object(launcher, 'gpu_devices',
                                                side_effect=lambda binary, backend: [(backend + '0', 'GPU')]))
                spawn = stack.enter_context(patch.object(launcher, '_spawn', side_effect=lambda *a: Mock()))
                engine = launcher.Launcher({}, say=lambda *_: None)
                stack.enter_context(patch.object(engine, '_gpu_ready',
                                                side_effect=lambda *a: engine.llm_acceleration == success))
                self.assertTrue(engine.start_llm())
                self.assertEqual([call.args[0][0] for call in spawn.call_args_list], expected)
                self.assertEqual(len(engine.procs), 1)

    def test_saved_cuda_choice_is_reused_on_resume(self):
        with tempfile.TemporaryDirectory() as root, patch.object(prepare, 'RUNTIME_DIR', root), \
                patch.object(prepare, 'get_llama', return_value=True) as get_llama, \
                patch.object(prepare, 'get_model', return_value=True), \
                patch.object(prepare, 'get_kiwix_tools', return_value=True), \
                contextlib.redirect_stdout(io.StringIO()):
            prepare.run(model='lfm3-1.7b', zims='none', oses='windows-x86_64', python=False, cuda=True, yes=True)
            self.assertTrue(json.loads((Path(root) / 'setup.json').read_text())['cuda'])
            get_llama.reset_mock()
            prepare.run(resume=True, yes=True)
            self.assertTrue(get_llama.call_args.args[2])
            prepare.run(resume=True, cuda=False, yes=True)
            self.assertFalse(get_llama.call_args.args[2])

    def test_cuda_offer_only_for_detected_nvidia(self):
        with patch.object(prepare, 'nvidia_available', return_value=False), patch('builtins.input') as ask:
            self.assertFalse(prepare.choose_cuda('en'))
            ask.assert_not_called()
        with patch.object(prepare, 'nvidia_available', return_value=True), patch('builtins.input', return_value=''):
            self.assertTrue(prepare.choose_cuda('en'))

    def test_nvidia_detection_handles_missing_or_broken_driver(self):
        with patch.object(prepare.shutil, 'which', return_value=None):
            self.assertFalse(prepare.nvidia_available())
        with patch.object(prepare.shutil, 'which', return_value='nvidia-smi'), \
                patch.object(prepare.subprocess, 'run', return_value=Mock(returncode=0, stdout='NVIDIA RTX\n')) as query:
            self.assertTrue(prepare.nvidia_available())
            query.return_value.returncode = 1
            self.assertFalse(prepare.nvidia_available())
            query.side_effect = OSError('missing driver')
            self.assertFalse(prepare.nvidia_available())

    def test_failed_companion_extraction_preserves_previous_cuda_install(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / 'llama.cpp/windows-x86_64-cuda'
            dest.mkdir(parents=True)
            (dest / 'llama-server.exe').write_bytes(b'old engine')
            (dest / 'cudart64_13.dll').write_bytes(b'old library')
            def download(url, path, **kwargs):
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_bytes(b'x')
            def extract(archive, target):
                if 'cudart' in archive:
                    raise OSError('incomplete CUDA archive')
                Path(target).mkdir(parents=True)
                (Path(target) / 'llama-server.exe').write_bytes(b'new engine')
            with patch.object(prepare, 'RUNTIME_DIR', root), \
                    patch.object(prepare, 'download', side_effect=download), \
                    patch.object(prepare, 'extract', side_effect=extract), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(prepare._install_llama('windows-x86_64', prepare.T['en'], 'new',
                    ('engine.zip', 'engine', 1), 'cuda', ('cudart.zip', 'runtime', 1)))
            self.assertEqual((dest / 'llama-server.exe').read_bytes(), b'old engine')
            self.assertEqual((dest / 'cudart64_13.dll').read_bytes(), b'old library')
