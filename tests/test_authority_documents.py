"""Offline source additions must retain conditions, provenance and existing guides."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.engine import Engine
from app.knowledge import KnowledgeBase, split_markdown

ROOT = Path(__file__).resolve().parents[1]
IDS = {'ifrc-2025', 'who-cfar', 'cdc-water', 'fema-ready', 'food-outage', 'who-snakebite'}


class AuthorityDocumentsTests(unittest.TestCase):
    def catalog(self):
        path = ROOT / 'config/authority-documents.json'
        self.assertTrue(path.exists(), 'The approved authority batch is not registered')
        return json.loads(path.read_text(encoding='utf-8'))['documents']

    def test_six_sources_have_bound_offline_summaries(self):
        docs = self.catalog()
        self.assertEqual({d['id'] for d in docs}, IDS)
        for d in docs:
            with self.subTest(source=d['id']):
                raw = (ROOT / d['summary_path']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), d['summary_sha256'])
                self.assertTrue(d['source_url'].startswith('https://'))
                for key in ('publisher', 'edition', 'audience', 'jurisdiction', 'rights', 'locator', 'checked_at'):
                    self.assertTrue(d[key], key)
                _, sections = split_markdown(raw.decode('utf-8'))
                self.assertEqual(len(sections), 1, 'Conditions must remain with the procedure')
                self.assertIn(d['source_url'], sections[0][2])
                self.assertIn('English', sections[0][2])

    def test_authority_sections_are_retrievable_with_conditions(self):
        cases = [
            ('unsafe accident scene hazards first aid', 'ifrc-2025', ('unsafe', 'help')),
            ('SBAR handover information ambulance', 'who-cfar', ('repeat', 'handover')),
            ('boil cloudy water elevation', 'cdc-water', ('6,500', '3 minutes', 'chemicals')),
            ('evacuation shelter plan accessible transport', 'fema-ready', ('local', 'flooded')),
            ('refrigerated soft cheese power outage temperature', 'food-outage', ('40°F', '2 hours', 'hard cheese')),
            ('snakebite carry stretcher transport', 'who-snakebite', ('carry', 'still', 'tourniquet')),
        ]
        kb = KnowledgeBase()
        engine = Engine({'kiwix_enabled': False, 'search_results': 5})
        for query, identity, conditions in cases:
            doc_id = 'authority/' + identity
            with self.subTest(source=identity):
                matches = [c for _, c in kb.search(query, k=8) if c.doc_id == doc_id]
                self.assertTrue(matches, identity)
                sources = engine.retrieve(query, 'en', use_kiwix=False)
                admitted = [s for s in sources if s.get('doc_id') == doc_id]
                self.assertTrue(admitted, [s.get('doc_id') for s in sources])
                for condition in conditions:
                    self.assertIn(condition.casefold(), admitted[0]['original_text'].casefold())

    def test_shipped_sources_are_upgrade_managed_not_personal_documents(self):
        from app.upgrade_app import managed
        for d in self.catalog():
            self.assertTrue(managed(d['summary_path']), d['summary_path'])
        kb = KnowledgeBase()
        self.assertIsNotNone(kb.get_doc('pt', 'authority/who-cfar'))
        source = next(c.to_dict() for _, c in kb.search('SBAR handover', 'pt', k=8)
                      if c.doc_id == 'authority/who-cfar')
        self.assertEqual(source['language'], 'en')

    def test_fuel_contaminated_floodwater_retrieves_water_prohibition(self):
        from app.query_planner import plan_query
        question = 'Floodwater smells of gasoline. Can I boil it for three minutes and drink it?'
        plan = plan_query(question, 'en')
        self.assertIn('water_chemical', plan.topics)
        self.assertNotIn('flood', plan.topics)
        engine = Engine({'kiwix_enabled': False})
        sources = engine.retrieve(question, 'en', use_kiwix=False)
        self.assertTrue(any(s.get('doc_id') == 'authority/cdc-water' for s in sources))
        # Ordinary flood evacuation must not become chemical-water treatment.
        self.assertNotIn('water_chemical', plan_query('Floodwater is rising around my car.', 'en').topics)

    def test_full_manuals_are_not_searchable_clinical_procedures(self):
        docs = self.catalog()
        self.assertEqual(next(d for d in docs if d['id'] == 'who-cfar')['activation'], 'handover_summary_only')
        text = (ROOT / 'knowledge/authorities/who-cfar.md').read_text()
        self.assertNotIn('uterine massage', text.lower())
        self.assertNotIn('deep wound packing', text.lower())
        self.assertFalse(list((ROOT / 'knowledge/authorities').glob('*.pdf')))

    def test_downloads_are_explicit_verified_and_outside_knowledge(self):
        self.catalog()  # Fail on missing registration before importing new command.
        from app.authority_documents import prepare_documents
        with tempfile.TemporaryDirectory() as folder, patch('app.authority_documents.download') as fetch:
            result = prepare_documents(Path(folder), ['who-cfar'])
            self.assertEqual(len(result), 1)
            args, kw = fetch.call_args
            self.assertEqual(kw['expected_size'], next(d for d in self.catalog() if d['id'] == 'who-cfar')['download']['bytes'])
            self.assertEqual(len(kw['sha256']), 64)
            self.assertEqual(Path(args[1]).parent, Path(folder) / 'runtime/authorities')
            self.assertTrue((Path(folder) / 'runtime/authorities/README.md').exists())

    def test_unverified_download_or_unknown_id_fails_before_network(self):
        self.catalog()
        from app.authority_documents import prepare_documents
        with tempfile.TemporaryDirectory() as folder, patch('app.authority_documents.download') as fetch:
            for ids in (['who-cfar', 'missing'], ['cdc-water']):
                with self.assertRaises(ValueError):
                    prepare_documents(Path(folder), ids)
                fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
