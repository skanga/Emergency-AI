"""Prohibition grammar must not invent permission or certify harm explanations."""
import json
from pathlib import Path
import unittest

from app.answer_validation import validate_answer

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'tests/evals/emergency_advice/baselines/snakebite-2026-11-26/draft-inspection.json'
QUESTION = 'I was bitten by an unidentified snake.'


def sources(text):
    return [dict(n=1,id='test',kind='kit',doc_title='Snakebite',section='First aid',text=text)]


class ProhibitionParsingTests(unittest.TestCase):
    def validate(self, text, evidence, lang='en'):
        return validate_answer(text, sources(evidence), QUESTION, lang)

    def test_negative_coordination_and_inflections(self):
        cases = [
            ('pt', 'Não aplique torniquete nem garrote', '**NÃO faça:** torniquete ou garrote'),
            ('pt', 'Não use torniquete arterial nem garrote', '**NÃO faça:** torniquete ou garrote'),
            ('es', 'No apliques un torniquete ni una banda apretada', '**NO haga:** torniquete o banda apretada'),
            ('es', 'No debe aplicar una banda apretada ni un torniquete', '**NO haga:** torniquete o banda apretada'),
            ('en', 'Do not use a tourniquet or a tight band', '**DO NOT:** tourniquets or tight bands'),
        ]
        for lang,answer,evidence in cases:
            with self.subTest(answer=answer):
                text,report=self.validate(answer+' [S1].',evidence,lang)
                self.assertTrue(text,report)
                self.assertTrue(report['claim_checks']['claims'])
                self.assertTrue(all(not c['positive'] for c in report['claim_checks']['claims']))

    def test_negative_source_lists_support_alcohol_ban(self):
        cases=[('pt','Não dê bebida alcoólica','**NÃO faça:** torniquete ou garrote, cortes, nem dar bebida alcoólica.'),
               ('es','No dé bebidas alcohólicas','**NO haga:** torniquete o ligadura, cortes, ni dar bebidas alcohólicas.'),
               ('en','Do not give alcoholic drinks','Do not cut the bite, nor give alcoholic drinks.')]
        for lang,answer,evidence in cases:
            with self.subTest(lang=lang):
                text,report=self.validate(answer+' [S1].',evidence,lang)
                self.assertTrue(text,report)
                self.assertTrue(report['claim_checks']['claims'])

    def test_alcohol_source_does_not_support_unrelated_prohibition(self):
        for answer in ('Do not give glucose','Do not give food','Do not give antihistamine tablets'):
            with self.subTest(answer=answer):
                text,report=self.validate(answer+' [S1].','Do not give alcoholic drinks.')
                self.assertFalse(text)
                self.assertIn('claim_not_supported_by_cited_passage',report['issues'])

    def test_alcohol_ban_can_be_one_item_in_a_larger_prohibited_list(self):
        text,report=self.validate('Do not give alcoholic drinks [S1].',
                                  'Do not give glucose or alcoholic drinks.')
        self.assertTrue(text,report)
        self.assertTrue(report['claim_checks']['claims'])

    def test_danger_with_explicit_prohibition_is_negative(self):
        for warning in ('Applying a tight arterial tourniquet is dangerous and should never be done',
                        'Tourniquets are dangerous and must not be used'):
            text,report=self.validate(warning+' [S1].','Never use a tight arterial tourniquet.')
            self.assertTrue(text,report)
            self.assertTrue(all(not c['positive'] for c in report['claim_checks']['claims']))

    def test_harm_explanation_is_unverified_warning_not_instruction(self):
        for warning in ('Tying a tight band above the bite is dangerous and can cause tissue damage',
                        'Tight bands can restrict blood flow excessively, causing tissue damage',
                        'Aplicar un torniquete puede dañar tejidos',
                        'Aplicar um torniquete pode causar danos aos tecidos'):
            with self.subTest(warning=warning):
                text,report=self.validate(warning+' [S1].','Never use a tight arterial tourniquet.')
                self.assertTrue(text,report)
                claims=report['claim_checks']['claims']
                self.assertTrue(claims)
                self.assertTrue(all(c['status']=='unverified' and c['claim_type']=='warning' and not c['evidence'] for c in claims))
                self.assertEqual(report['claim_support'],'not_verified')

    def test_harm_warning_cannot_supply_prohibition_evidence(self):
        text,report=self.validate('Do not apply a tourniquet [S1].','Tourniquets can cause tissue damage.')
        self.assertFalse(text)
        self.assertIn('claim_not_supported_by_cited_passage',report['issues'])

    def test_negation_and_warning_do_not_hide_positive_action(self):
        for draft in ('Do not panic; apply a tourniquet [S1].',
                      'Tourniquets can cause damage, but apply one [S1].',
                      'A tourniquet can cause damage; use it anyway [S1].',
                      'Tourniquets can cause damage and apply one anyway [S1].',
                      'No debe aplicar un torniquete salvo si no hay hinchazón [S1].',
                      'Não use torniquete a menos que conheça a espécie [S1].'):
            with self.subTest(draft=draft):
                text,report=self.validate(draft,'Never use a tourniquet.')
                self.assertFalse(text)
                self.assertIn('snake_tourniquet_unsafe',report['issues'])

    def test_heading_scope_stops_at_new_sentence(self):
        for evidence in ('DO NOT: cut the wound. Apply a tourniquet.',
                         'NÃO faça: cortes. Aplique um torniquete.',
                         'NO haga: cortes. Aplique un torniquete.'):
            text,report=self.validate('Never use a tourniquet [S1].',evidence)
            self.assertFalse(text)
            self.assertIn('claim_not_supported_by_cited_passage',report['issues'])

    def test_captured_portuguese_prohibitions_remain_supported(self):
        row=next(r for r in json.loads(CAPTURE.read_text(encoding='utf-8'))['results'] if r['id']=='snake_pressure_pt' and r['trial']==1)
        c=row['validation_inputs'][0];q=row['request']
        text,report=validate_answer(c['draft'],c['sources'],q['q'],q['lang'])
        # The later water rule now checks a previously unrecognized instruction.
        # Its source says only conscious, not safe swallowing, so the whole
        # historical draft no longer passes even though its bans are supported.
        self.assertFalse(text)
        self.assertNotIn('oral_intake_prerequisites_missing', report['issues'])
        self.assertIn('claim_not_supported_by_cited_passage', report['issues'])
        bans = [c for c in report['claim_checks']['claims'] if c['rule'] == 'snake_tourniquet']
        self.assertTrue(bans)
        self.assertTrue(all(c['status'] == 'pattern_supported' for c in bans))

    def test_captured_real_safety_failures_remain_blocked(self):
        for row in json.loads(CAPTURE.read_text(encoding='utf-8'))['results']:
            if not ((row['id']=='snake_pressure' and row['trial']==2) or row['id']=='snake_pressure_es'):continue
            with self.subTest(case=(row['id'],row['trial'])):
                c=row['validation_inputs'][0];q=row['request']
                text,report=validate_answer(c['draft'],c['sources'],q['q'],q['lang'])
                self.assertFalse(text)
                self.assertIn('snake_tourniquet_unsafe',report['issues'])

    def test_captured_negative_and_warning_clauses_are_not_positive(self):
        for row in json.loads(CAPTURE.read_text(encoding='utf-8'))['results']:
            c=row['validation_inputs'][0];q=row['request']
            _,report=validate_answer(c['draft'],c['sources'],q['q'],q['lang'])
            for claim in report['claim_checks']['claims']:
                if claim['rule']=='snake_tourniquet':
                    with self.subTest(case=(row['id'],row['trial']),span=claim['answer_span']):
                        self.assertFalse(claim['positive'])
