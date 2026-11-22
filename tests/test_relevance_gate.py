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

    def test_no_sources_without_model(self):
        engine = Engine({'kiwix_enabled': False})
        engine.llm = Mock(return_value=None)
        answer, sources, info = engine.answer_text(
            'write a python script to compute the 1st 15 fibonacci numbers')
        self.assertEqual([], sources)
        self.assertIn('nothing in the kit', answer)
        self.assertEqual('model_unavailable', info['reason'])

    def test_no_sources_uses_labeled_general_knowledge(self):
        engine = Engine({'kiwix_enabled': False})
        model = Mock()
        model.options.return_value = {'context': 8192, 'max_tokens': 2048, 'context_margin': 256}
        model.count_prompt.return_value = 100
        model.stream_chat.return_value = iter(['Python code'])
        model.describe.return_value = {'model': 'test'}
        engine.llm = Mock(return_value=model)
        answer, sources, info = engine.answer_text('write a python script to compute fibonacci')
        self.assertEqual([], sources)
        self.assertIn('Not backed by local sources', answer)
        self.assertIn('Python code', answer)
        self.assertFalse(info['sources_supplied'])
        self.assertNotIn('grounded', info)
        self.assertEqual('llm', info['mode'])

    def test_supplied_sources_are_not_claimed_as_verified(self):
        engine = Engine({'kiwix_enabled': False})
        before = engine.retrieve('How do I sharpen a knife?', 'en')
        model = Mock()
        model.options.return_value = {'context': 8192, 'max_tokens': 2048, 'context_margin': 256}
        model.count_prompt.return_value = 100
        model.stream_chat.return_value = iter(['Answer'])
        engine.llm = Mock(return_value=model)
        answer, sources, info = engine.answer_text('How do I sharpen a knife?')
        self.assertEqual([s['id'] for s in before], [s['id'] for s in sources])
        self.assertTrue(info['sources_supplied'])
        self.assertNotIn('grounded', info)
        self.assertIn('citations are not independently verified', answer)

    def test_ai_disabled_is_not_model_unavailable(self):
        engine = Engine({'kiwix_enabled': False})
        engine.llm = Mock()
        _, _, info = engine.answer_text('fibonacci', use_llm=False)
        self.assertEqual('ai_disabled', info['reason'])
        engine.llm.assert_not_called()

    def test_prompt_switches_only_without_usable_sources(self):
        engine = Engine({'kiwix_enabled': False})
        from app import i18n
        for lang in ('en', 'pt', 'es'):
            self.assertEqual(i18n.general_knowledge_prompt(lang),
                             engine.build_messages('question', lang, [])[0]['content'])
            source = {'n': 1, 'kind': 'kit', 'doc_title': 'Guide', 'section': 'Topic', 'text': 'Evidence'}
            self.assertEqual(i18n.SYSTEM_PROMPT[lang],
                             engine.build_messages('question', lang, [source])[0]['content'])
            source['context_omitted'] = True
            self.assertEqual(i18n.general_knowledge_prompt(lang),
                             engine.build_messages('question', lang, [source])[0]['content'])

    def test_incidental_matches_are_rejected(self):
        query = 'write a python script to compute the 1st 15 fibonacci numbers'
        for passage in ['A computer uses 15 W.', 'Write down everything you learn.',
                        'Use the same number of strokes at 15 degrees.']:
            with self.subTest(passage=passage):
                self.assertFalse(is_relevant(query, passage))
