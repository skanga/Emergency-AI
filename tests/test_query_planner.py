import json
import unittest
from pathlib import Path

from app.query_planner import plan_query


class QueryPlannerTests(unittest.TestCase):
    def test_original_cases_have_bounded_multilingual_topics(self):
        cases = json.loads(Path('tests/fixtures/retrieval/cases.json').read_text())
        expected = ['anaphylaxis', 'anaphylaxis', 'bleeding', 'burn', 'carbon_monoxide', 'cpr', 'dehydration', 'diabetes', 'flood', 'food_safety', 'fire', 'heatstroke', 'choking', 'cpr', 'poison', 'carbon_monoxide', 'seizure', 'snakebite', 'cpr', 'stroke', 'water_disinfection', 'water_chemical', 'electrical']
        for case, topic in zip(cases, expected):
            req = case['request']
            with self.subTest(case=case['id']):
                plan = plan_query(req['q'], req['lang'], req['history'])
                self.assertIn(topic, plan.topics)
                self.assertEqual(set(plan.queries_by_language), {'en', 'es', 'pt'})
                self.assertTrue(all(1 <= len(q) <= 2 for q in plan.queries_by_language.values()))
        self.assertEqual(plan_query(**{'question': cases[13]['request']['q'], 'history': cases[13]['request']['history']}).scope['age_group'], 'infant')

    def test_whole_words_unknowns_and_nonmedical_context(self):
        for query in ('My camera is unresponsive', 'engine gasping', 'burnished copper', 'seizureproof camera'):
            plan = plan_query(query)
            self.assertEqual(plan.topics, ())
            self.assertTrue(plan.limited_cross_language)
            self.assertEqual(set(plan.queries_by_language), {'en'})

    def test_recent_user_history_and_override(self):
        history = [{'role': 'user', 'content': 'My infant is choking'}, {'role': 'assistant', 'content': 'stroke seizure'}]
        plan = plan_query('He is an adult, not choking. Now unconscious and not breathing.', history=history)
        self.assertEqual(plan.scope['age_group'], 'adult')
        self.assertIn('choking', plan.scope['negated_facts'])
        self.assertNotIn('choking', plan.topics)
        self.assertIn('cpr', plan.topics)
        reset = plan_query('New question: how do I repair my camera?', history=history)
        self.assertEqual(reset.context_terms, ())
        self.assertEqual(reset.topics, ())

    def test_multilingual_symptoms(self):
        for text, lang, topic in [('Não responde e está ofegante', 'pt', 'cpr'), ('Bebé atragantado no puede respirar', 'es', 'choking'), ('Língua inchada e chiado após amendoim', 'pt', 'anaphylaxis')]:
            self.assertIn(topic, plan_query(text, lang).topics)

    def test_source_language_codes_and_negated_age(self):
        from app.query_planner import normalize_language
        self.assertEqual(normalize_language('eng'), 'en')
        self.assertEqual(normalize_language('por'), 'pt')
        self.assertEqual(normalize_language('spa'), 'es')
        self.assertEqual(normalize_language('pt-BR'), 'pt')
        self.assertEqual(plan_query('not an infant, an adult choking').scope['age_group'], 'adult')
        self.assertEqual(plan_query('camera manual', 'eng').request_language, 'en')

    def test_numeric_ages_and_locales(self):
        for text, expected in [('A 64-year-old man collapsed', 'adult'), ('18 months old choking', 'child'), ('8 months old choking', 'infant'), ('bebê de 18 meses engasgado', 'child'), ('niño de 8 meses atragantado', 'infant'), ('adulto de 64 anos', 'adult')]:
            with self.subTest(text=text):
                self.assertEqual(plan_query(text).scope['age_group'], expected)

    def test_history_correction_persists(self):
        history = [{'role': 'user', 'content': 'My infant is choking'}, {'role': 'user', 'content': 'He is not choking anymore, but unresponsive and gasping'}]
        plan = plan_query('What should I do next?', history=history)
        self.assertIn('cpr', plan.topics)
        self.assertNotIn('choking', plan.topics)
        self.assertIn('choking', plan.scope['negated_facts'])
        self.assertEqual(plan.scope['age_group'], 'infant')

    def test_negative_unrelated_topic_does_not_reset_history(self):
        plan = plan_query('He is not bleeding. What should I do?', history=[{'role': 'user', 'content': 'My infant is choking'}])
        self.assertIn('choking', plan.topics)
        self.assertEqual(plan.scope['age_group'], 'infant')
        self.assertIn('bleeding', plan.scope['negated_facts'])

    def test_equipment_does_not_suppress_explicit_emergency(self):
        plan = plan_query('The engine is running in the garage and there is carbon monoxide')
        self.assertIn('carbon_monoxide', plan.topics)
        self.assertEqual(set(plan.queries_by_language), {'en', 'pt', 'es'})
        self.assertEqual(plan_query('How does a four stroke engine work?').topics, ())
