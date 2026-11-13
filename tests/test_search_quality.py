"""Expected source sections for multilingual information and practical queries."""
import unittest
from app.knowledge import KnowledgeBase


class SearchQualityTests(unittest.TestCase):
    def test_other_topics_stay_relevant(self):
        kb = KnowledgeBase()
        cases = [('en', 'purify water', '01-water'), ('pt', 'purificar agua', '01-water'),
                 ('es', 'purificar agua', '01-water'), ('en', 'light a campfire', '02-fire'),
                 ('pt', 'acender fogo', '02-fire'), ('es', 'encender fuego', '02-fire')]
        for lang, question, expected in cases:
            with self.subTest(lang=lang, question=question):
                self.assertIn(expected, [c.doc_id for _, c in kb.search(question, lang, k=3)])

    def test_information_queries_find_devices_section(self):
        kb = KnowledgeBase()
        queries = {
            'en': ['How should I keep offline information available during a power or internet outage?',
                   'Where should I store backup copies of the offline kit?'],
            'pt': ['Como manter as informações offline disponíveis quando falta energia ou internet?',
                   'Onde guardar cópias dos dados e bases Kiwix?'],
            'es': ['¿Cómo mantener disponible la información sin conexión durante un corte de electricidad o internet?',
                   'Dónde guardar copias de los datos y bases Kiwix?'],
        }
        for lang, questions in queries.items():
            for question in questions:
                with self.subTest(lang=lang, question=question):
                    results = kb.search(question, lang, k=3)
                    self.assertTrue(any(c.doc_id == '10-energy-light' and
                                        c.anchor in ('devices-and-data', 'dispositivos-e-dados', 'dispositivos-y-datos')
                                        for _, c in results))
