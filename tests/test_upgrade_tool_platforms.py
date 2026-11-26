"""Cross-platform catalog and package-layout regression tests (no native execution)."""
import hashlib
import io
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app import document_tools, upgrade_tools
from app.upgrade_assets import verify_document


class ToolPlatformTests(unittest.TestCase):
    def test_reviewed_platform_catalogs(self):
        for component, platforms in {
            'kiwix-tools': ['windows-x86_64', 'macos-x86_64', 'macos-arm64', 'linux-arm64'],
            'document-tools': ['windows-x86_64', 'macos-x86_64', 'macos-arm64'],
        }.items():
            for platform in platforms:
                with self.subTest(component=component, platform=platform):
                    entry = upgrade_tools.catalog(component, platform)
                    self.assertEqual(entry['verification'], 'project-pinned-sha256')
                    self.assertGreater(entry['size'], 0)
        for component, platform in [('kiwix-tools', 'windows-arm64'), ('document-tools', 'linux-arm64'), ('document-tools', 'windows-arm64')]:
            with self.assertRaises(ValueError):
                upgrade_tools.catalog(component, platform)

    def test_windows_pdf_layout_and_version_output(self):
        entry = {'root': 'xpdf', 'binary': 'bin64/pdftotext.exe', 'pdfinfo': 'bin64/pdfinfo.exe',
                 'documentation': 'doc/pdftotext.txt', 'version': '4.06'}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'xpdf'
            for name in [entry['binary'], entry['pdfinfo'], entry['documentation'], 'README', 'COPYING', 'COPYING3']:
                path = folder/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            with patch.object(document_tools, '_artifact', return_value=entry):
                self.assertEqual(document_tools.tool_status(temp, 'windows-x86_64')['state'], 'available')
            def version(command, **kwargs):
                return subprocess.CompletedProcess(command, 99, b'', (Path(command[0]).stem+' version 4.06\n').encode())
            with patch('app.upgrade_assets.subprocess.run', side_effect=version):
                verify_document(folder, entry)

    def test_adopt_flat_windows_kiwix_distribution(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, 'w') as archive:
            archive.writestr('kiwix-serve.exe', b'fixture')
            archive.writestr('icuuc74.dll', b'library')
        data = payload.getvalue()
        entry = {'root': None, 'version': '3.8.1', 'url': 'https://download.kiwix.org/release/kiwix-tools/test.zip',
                 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'runtime/kiwix-tools/windows-x86_64'
            folder.mkdir(parents=True)
            (folder/'kiwix-serve.exe').write_bytes(b'fixture')
            (folder/'icuuc74.dll').write_bytes(b'library')
            def download(candidate, stage):
                archive = stage/'test.zip'; archive.write_bytes(data); return archive
            with patch.object(upgrade_tools, 'catalog', return_value=entry), patch.object(upgrade_tools, 'platform_key', return_value='windows-x86_64'), patch.object(upgrade_tools, '_download', side_effect=download), patch.object(upgrade_tools, 'verify_tool'):
                installed = upgrade_tools.adopt_tool(Path(temp), 'kiwix-tools')
            upgrade_tools.verify_installed(Path(temp), installed)
            self.assertEqual(len(installed['files']), 2)
