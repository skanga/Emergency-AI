import json
import contextlib
import io
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path
from app import prepare


class ZimLanguagesTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(Path('config/zims.json').read_text(encoding='utf-8'))

    def test_download_resume_and_archives(self):
        with tempfile.TemporaryDirectory() as root, \
                patch.object(prepare, 'RUNTIME_DIR', root), \
                patch.object(prepare, 'ZIM_DIR', root), \
                patch.object(prepare, 'get_zim', return_value=True) as download, \
                patch.object(prepare, 'get_archive', return_value=True) as archive, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            args = dict(model='none', zims='full', oses='this', python=False,
                        yes=True, skip_tools=True, zim_languages='pt', archives='wikihow-es')
            self.assertEqual(prepare.run(**args), 0)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(archive.call_args.args[0]['id'], 'wikihow-es')
            self.assertIn('wikipedia_pt_all [pt] ~6.59 GiB', output.getvalue())
            info = json.loads(Path(root, 'kit-info.json').read_text())
            self.assertEqual(info['zim_languages'], 'pt')
            download.reset_mock()
            self.assertEqual(prepare.run(resume=True, yes=True, skip_tools=True), 0)
            self.assertEqual(download.call_count, 2)
            download.reset_mock()
            self.assertEqual(prepare.run(resume=True, yes=True, skip_tools=True, zim_languages='es'), 0)
            self.assertTrue(all(c.args[0]['lang'] == 'es' for c in download.call_args_list))
            saved = json.loads(Path(root, 'setup.json').read_text())
            saved.pop('zim_languages')
            saved.pop('include_english_references')
            Path(root, 'setup.json').write_text(json.dumps(saved))
            download.reset_mock()
            self.assertEqual(prepare.run(resume=True, yes=True, skip_tools=True), 0)
            self.assertEqual(download.call_count, 15)

    def test_interactive_default_and_empty_retry(self):
        for profile, answers, expected in [('full', [''], 2), ('minimal', ['', 'none'], 0)]:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as root, \
                    patch.object(prepare, 'RUNTIME_DIR', root), \
                    patch.object(prepare, 'ZIM_DIR', root), \
                    patch.object(prepare, 'get_zim', return_value=True) as download, \
                    patch.object(prepare, '_ask', side_effect=['recommended', 'none', profile, 'this']), \
                    patch.object(prepare, '_yes', side_effect=[False, True]), \
                    patch('builtins.input', side_effect=answers) as prompt, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(prepare.run(lang='pt', python=False, skip_tools=True), 0)
                self.assertEqual(download.call_count, expected)
                self.assertIn('[pt]', prompt.call_args_list[0].args[0])

    def test_portuguese_only(self):
        entries = prepare.select_zims(self.cfg, 'full', 'pt', False)
        self.assertEqual({e['name'] for e in entries}, {'wikipedia_pt_all', 'wikipedia_pt_medicine'})

    def test_references_not_english_wikipedia(self):
        entries = prepare.select_zims(self.cfg, 'full', 'pt', True)
        names = [e['name'] for e in entries]
        self.assertIn('zimgit-water_en', names)
        self.assertIn('ifixit_en_all', names)
        self.assertNotIn('wikipedia_en_all', names)
        self.assertNotIn('wikivoyage_en_all', names)
        self.assertEqual(len(names), len(set(names)))

    def test_all_and_bilingual(self):
        self.assertEqual(len(prepare.select_zims(self.cfg, 'full', 'all', False)), 15)
        self.assertEqual(len(prepare.select_zims(self.cfg, 'full', 'pt,es', False)), 4)

    def test_empty_and_invalid(self):
        self.assertEqual(prepare.select_zims(self.cfg, 'minimal', 'pt', False), [])
        for value in ('xx', '', 'all,pt'):
            with self.assertRaises(ValueError):
                prepare.select_zims(self.cfg, 'full', value, False)
