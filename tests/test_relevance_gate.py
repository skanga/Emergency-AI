"""Conservative source filtering: prefer recall over precision."""
import unittest
from unittest.mock import Mock

from app.engine import Engine
from app.knowledge import KnowledgeBase, is_relevant


class RelevanceGateTests(unittest.TestCase):
    def test_fibonacci_does_not_return_survival_guides(self):
        self.assertEqual([], KnowledgeBase().search(
            'write a python script to compute the 1st 15 fibonacci numbers'))

    def test_meaningful_matches_survive(self):
        cases = [
            ('write a python script to compute the 1st 15 fibonacci numbers', 'Python programming guide'),
            ('write a python script to compute fibonacci', 'Fibonacci sequence implementation'),
            ('sharpen a knife at 15 degrees', 'Keep the knife at 15 degrees.'),
            ('numbers', 'The numbers are approximate.'),
            ('how to write', 'Write down your observations.'),
            ('purify water', 'Boil before drinking.'),
            ('purificar agua', 'Ferver antes de beber.'),
            ('purificar agua', 'Hervir antes de beber.'),
            ('burns', 'Treat a burn carefully.'),
        ]
        for query, passage in cases:
            with self.subTest(query=query, passage=passage):
                self.assertTrue(is_relevant(query, passage))

    def test_kiwix_filters_content_before_numbering(self):
        engine = Engine({'kiwix_enabled': True})
        engine.kb.search = Mock(return_value=[])
        engine.kiwix_ok = Mock(return_value=True)
        engine.kiwix.search = Mock(return_value=[
            {'link': '/bad', 'book': 'Library', 'title': 'Python', 'book_name': 'test'},
            {'link': '/good', 'book': 'Library', 'title': 'Programming', 'book_name': 'test'},
        ])
        engine.kiwix.article_text = Mock(side_effect=[
            'A computer uses 15 W.', 'Python script for Fibonacci numbers.'])
        sources = engine.retrieve('write a python script to compute the 1st 15 fibonacci numbers', 'en')
        self.assertEqual(['/good'], [s['link'] for s in sources])
        self.assertEqual([1], [s['n'] for s in sources])

    def test_no_sources_skips_model(self):
        engine = Engine({'kiwix_enabled': False})
        engine.llm = Mock()
        answer, sources, info = engine.answer_text(
            'write a python script to compute the 1st 15 fibonacci numbers')
        self.assertEqual([], sources)
        self.assertIn('nothing in the kit', answer)
        engine.llm.assert_not_called()

    def test_incidental_matches_are_rejected(self):
        query = 'write a python script to compute the 1st 15 fibonacci numbers'
        for passage in ['A computer uses 15 W.', 'Write down everything you learn.',
                        'Use the same number of strokes at 15 degrees.']:
            with self.subTest(passage=passage):
                self.assertFalse(is_relevant(query, passage))
