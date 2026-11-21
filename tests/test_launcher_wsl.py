import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import launcher


class WslEnvironmentTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(temp)
        self.lib = self.root / 'lib'
        self.drivers = self.root / 'drivers'
        self.lib.mkdir()
        self.drivers.mkdir()
        (self.lib / 'libcuda.so.1').write_text('active driver')
        self.enterContext(patch.object(launcher, '_WSL_LIB_DIR', str(self.lib), create=True))
        self.enterContext(patch.object(launcher, '_WSL_DRIVERS_DIR', str(self.drivers), create=True))
        self.enterContext(patch('platform.release', return_value='6.6-microsoft-standard-WSL2'))
        self.enterContext(patch.object(launcher.sys, 'platform', 'linux'))
        self.enterContext(patch.object(launcher, 'is_windows', return_value=False))
        self.enterContext(patch.dict(os.environ, {'LD_LIBRARY_PATH': '/inherited'}, clear=True))

    def driver(self, name, matching=True, compiler=True):
        directory = self.drivers / name
        directory.mkdir()
        if matching:
            os.link(self.lib / 'libcuda.so.1', directory / 'libcuda.so.1.1')
        else:
            (directory / 'libcuda.so.1.1').write_text('old driver')
        if compiler:
            (directory / 'libnvidia-ptxjitcompiler.so.1').touch()
        return directory

    def test_matches_active_driver_hardlink_instead_of_first_directory(self):
        self.driver('old', matching=False)
        active = self.driver('active')
        env = launcher._env_for('/kit/llama-server', backend='cuda')
        self.assertEqual(env['LD_LIBRARY_PATH'], os.pathsep.join([str(active), '/kit', '/inherited']))
        self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/inherited')

    def test_complete_wsl_lib_pair_takes_precedence(self):
        (self.lib / 'libnvidia-ptxjitcompiler.so.1').touch()
        self.driver('active')
        env = launcher._env_for('/kit/llama-server', backend='cuda')
        self.assertEqual(env['LD_LIBRARY_PATH'], os.pathsep.join([str(self.lib), '/kit', '/inherited']))

    def test_forwarding_library_uses_the_only_complete_driver_directory(self):
        active = self.driver('forwarded-driver', matching=False)
        env = launcher._env_for('/kit/llama-server', backend='cuda')
        self.assertEqual(env['LD_LIBRARY_PATH'], os.pathsep.join([str(active), '/kit', '/inherited']))

    def test_forwarding_library_with_multiple_drivers_does_not_guess(self):
        self.driver('driver1', matching=False)
        self.driver('driver2', matching=False)
        env = launcher._env_for('/kit/llama-server', backend='cuda')
        self.assertEqual(env['LD_LIBRARY_PATH'], os.pathsep.join(['/kit', '/inherited']))

    def test_ambiguous_or_incomplete_driver_is_not_guessed(self):
        self.driver('incomplete', compiler=False)
        self.assertEqual(launcher._env_for('/kit/llama-server', backend='cuda')['LD_LIBRARY_PATH'],
                         os.pathsep.join(['/kit', '/inherited']))
        self.driver('active1')
        self.driver('active2')
        self.assertEqual(launcher._env_for('/kit/llama-server', backend='cuda')['LD_LIBRARY_PATH'],
                         os.pathsep.join(['/kit', '/inherited']))

    def test_missing_or_inaccessible_driver_store_preserves_fallback(self):
        for error in [FileNotFoundError(), PermissionError()]:
            with self.subTest(error=type(error).__name__), patch.object(launcher.os, 'scandir', side_effect=error):
                self.assertEqual(launcher._env_for('/kit/llama-server', backend='cuda')['LD_LIBRARY_PATH'],
                                 os.pathsep.join(['/kit', '/inherited']))

    def test_path_entries_are_deduplicated_without_current_directory(self):
        active = self.driver('active')
        with patch.dict(os.environ, {'LD_LIBRARY_PATH': os.pathsep.join(['', str(active), '/kit', '', '/inherited', '/inherited', ''])}):
            env = launcher._env_for('/kit/llama-server', backend='cuda')
        self.assertEqual(env['LD_LIBRARY_PATH'], os.pathsep.join([str(active), '/kit', '/inherited']))

    def test_native_linux_does_not_use_wsl_libraries(self):
        self.driver('active')
        with patch('platform.release', return_value='6.8-generic'):
            env = launcher._env_for('/kit/llama-server', backend='cuda')
        self.assertEqual(env['LD_LIBRARY_PATH'], os.pathsep.join(['/kit', '/inherited']))

    def test_kiwix_and_other_backends_do_not_use_wsl_libraries(self):
        self.driver('active')
        for backend in [None, 'vulkan', 'cpu']:
            with self.subTest(backend=backend):
                env = launcher._env_for('/kit/server', backend=backend)
                self.assertEqual(env['LD_LIBRARY_PATH'], os.pathsep.join(['/kit', '/inherited']))
                self.assertEqual(env['NO_PROXY'], '127.0.0.1,localhost')

    def test_macos_and_windows_keep_platform_environment(self):
        self.driver('active')
        with patch.object(launcher.sys, 'platform', 'darwin'):
            env = launcher._env_for('/kit/llama-server', backend='metal')
            self.assertTrue(env['DYLD_LIBRARY_PATH'].startswith('/kit'))
            self.assertEqual(env['LD_LIBRARY_PATH'], '/inherited')
        with patch.object(launcher.sys, 'platform', 'win32'), patch.object(launcher, 'is_windows', return_value=True):
            env = launcher._env_for('/kit/llama-server', backend='cuda')
            self.assertEqual(env['LD_LIBRARY_PATH'], '/inherited')


if __name__ == '__main__':
    unittest.main()
