from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.document_tools import tool_status, prepare_tool


class DocumentToolTests(unittest.TestCase):
    def test_missing_and_unsupported_never_download(self):
        with tempfile.TemporaryDirectory() as root, patch('app.document_tools.download') as download:
            self.assertEqual(tool_status(root, 'linux-x86_64')['state'], 'extractor_missing')
            self.assertEqual(tool_status(root, 'other-platform')['state'], 'unsupported_platform')
            with self.assertRaises(ValueError):
                prepare_tool(root, 'other-platform')
            download.assert_not_called()

    def test_preparation_uses_pinned_hash_and_keeps_license_tree(self):
        with tempfile.TemporaryDirectory() as root:
            def unpack(archive, destination):
                base = Path(destination) / 'xpdf-tools-linux-4.06'
                (base / 'bin64').mkdir(parents=True)
                (base / 'doc').mkdir()
                for file in ['bin64/pdftotext','bin64/pdfinfo','README','COPYING','COPYING3','doc/pdftotext.1']:
                    (base / file).write_text('fixture')
            with patch('app.document_tools.download') as download, patch('app.document_tools.extract', side_effect=unpack):
                state = prepare_tool(root, 'linux-x86_64')
            self.assertEqual(state['state'], 'available')
            self.assertEqual(len(download.call_args.kwargs['sha256']), 64)
            self.assertTrue((Path(state['path']).parent.parent / 'COPYING3').is_file())
