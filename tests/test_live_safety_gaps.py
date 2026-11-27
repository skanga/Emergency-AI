"""Regressions from the fresh multilingual run, including masked hazards."""
import json
from pathlib import Path
import unittest

from app.answer_validation import validate_answer
from app.guidance import guidance_sources, fallback_answer
from app.query_planner import plan_query

BASE = Path(__file__).parent / 'evals/emergency_advice/baselines/snakebite-2026-11-26'
Q = 'An unidentified snake bit my leg.'


def source(text):
    return [dict(n=1, id='test', kind='kit', text=text)]


class LiveSafetyGapsTests(unittest.TestCase):
    def test_masked_hazards_are_detected_without_unrelated_blockers(self):
        data = json.loads((BASE / 'steps34-live-review.json').read_text())
        rows = json.loads((BASE / 'steps34-live-inspection.json').read_text())['results']
        for probe in data['ablation_probes']:
            row = next(r for r in rows if f"{r['id']}#{r['trial']}" == probe['key'])
            issue = ('snake_compression_condition_unsafe' if probe['key'] == 'snake_pressure_es#1'
                     else 'oral_intake_prerequisites_missing')
            with self.subTest(case=probe['key']):
                _, report = validate_answer(probe['draft'], row['validation_inputs'][0]['sources'],
                                            row['request']['q'], row['request']['lang'])
                self.assertIn(issue, report['issues'])

    def test_water_requires_awake_and_swallowing_in_each_language(self):
        for bad, good in (
            ('If conscious, offer small sips of water', 'If conscious and able to swallow safely, offer small sips of water'),
            ('Si está consciente, ofrézcale agua para beber', 'Si está consciente y puede tragar, ofrézcale agua para beber'),
            ('Se estiver consciente, ofereça água', 'Se estiver consciente e consegue engolir, ofereça água'),
        ):
            with self.subTest(bad=bad):
                _, report = validate_answer(bad+' [S1].', source(good), Q)
                self.assertIn('oral_intake_prerequisites_missing', report['issues'])
                answer, report = validate_answer(good+' [S1].', source(good), Q)
                self.assertTrue(answer, report)
                self.assertTrue(report['claim_checks']['claims'])
                _, report = validate_answer(good.replace(' and ', ' or ').replace(' y ', ' o ').replace(' e ', ' ou ')+' [S1].', source(good), Q)
                self.assertIn('oral_intake_prerequisites_missing', report['issues'])

    def test_water_is_not_topical_washing_or_unrelated_food_evidence(self):
        text, report = validate_answer('Wash the bite with water [S1].', source('Wash the bite with water.'), Q)
        self.assertTrue(text, report)
        _, report = validate_answer('If conscious and able to swallow, offer water [S1].',
                                    source('If conscious and able to swallow, offer glucose.'), Q)
        self.assertIn('claim_not_supported_by_cited_passage', report['issues'])

    def test_negative_swallowing_and_portuguese_capability(self):
        good = 'Ofereça água apenas se a pessoa estiver consciente e capaz de engolir com segurança'
        text, report = validate_answer(good+' [S1].', source(good), Q, 'pt')
        self.assertTrue(text, report)
        for bad in ('Se está consciente mas não é capaz de engolir, ofereça água',
                    'Si está consciente pero no es capaz de tragar, ofrézcale agua'):
            with self.subTest(bad=bad):
                _, report = validate_answer(bad+' [S1].', source(good), Q)
                self.assertIn('oral_intake_prerequisites_missing', report['issues'])

    def test_carrying_citation_does_not_authorize_support_you_alternative(self):
        _, report = validate_answer('Have helpers carry you on a stretcher or support you to the road [S1].',
                                    source('Have helpers carry you on a stretcher.'), Q)
        self.assertIn('transport_method_not_supported', report['issues'])

    def test_compression_verb_inflections_and_noun_order(self):
        for instruction in ('Aplíquese vendaje compresivo', 'Aplique bandagem compressiva',
                            'Apply a pressure bandage', 'Use compression bandaging'):
            with self.subTest(instruction=instruction):
                _, report = validate_answer(instruction+' [S1].', source(instruction), Q)
                self.assertIn('snake_compression_scope_missing', report['issues'])

    def test_known_region_does_not_authorize_inverted_swelling_condition(self):
        evidence = 'In Australia, apply a pressure bandage for neurotoxic bites without local swelling.'
        _, report = validate_answer('Apply a pressure bandage if there is local swelling [S1].',
                                    source(evidence), 'A snake bit me in Australia.')
        self.assertIn('snake_compression_condition_unsafe', report['issues'])

    def test_prohibition_list_heading_has_bounded_scope(self):
        evidence = 'Never use a tourniquet.'
        for heading, action in [('**DO NOT:**', 'Apply a tourniquet'),
                                ('**NÃO faça:**', 'Aplique um torniquete'),
                                ('**NO haga:**', 'Aplique un torniquete')]:
            with self.subTest(heading=heading):
                draft = heading+'\n* '+action+' [S1].'
                text, report = validate_answer(draft, source(evidence), Q)
                self.assertTrue(text, report)
                text, report = validate_answer(draft+'\n\n**Now:**\n* Apply a tourniquet [S1].', source(evidence), Q)
                self.assertFalse(text)
                self.assertIn('snake_tourniquet_unsafe', report['issues'])
                text, report = validate_answer('Never use a tourniquet [S1].', source(heading+'\n* '+action+'.'), Q)
                self.assertTrue(text, report)

    def test_emphasis_is_not_exception_but_exception_still_blocks(self):
        for phrase in ('Never use a tourniquet, especially when the species is unknown',
                       'Não use torniquete, especialmente quando a espécie é desconhecida',
                       'No use un torniquete, especialmente cuando la especie es desconocida'):
            with self.subTest(phrase=phrase):
                text, report = validate_answer(phrase+' [S1].', source('Never use a tourniquet.'), Q)
                self.assertTrue(text, report)
                _, report = validate_answer(phrase+' unless help is delayed [S1].', source('Never use a tourniquet.'), Q)
                self.assertIn('snake_tourniquet_unsafe', report['issues'])

    def test_scoped_danger_explanation_remains_unverified(self):
        draft = 'For an unidentified snakebite, applying a tight band is dangerous and can worsen injury.'
        text, report = validate_answer(draft, source('Never use a tourniquet.'), Q)
        self.assertTrue(text, report)
        self.assertEqual(report['claim_checks']['claims'][0]['status'], 'unverified')
        _, report = validate_answer(draft+' However, apply one [S1].', source('Never use a tourniquet.'), Q)
        self.assertIn('snake_tourniquet_unsafe', report['issues'])

    def test_compound_plain_prohibition_can_link_but_extra_claim_cannot(self):
        for intro in ('Do not tie a tight band or apply a tourniquet.', 'Do not tie a tight band (tourniquet) above the bite.'):
            text, report = validate_answer(intro+'\nNever use a tourniquet [S1].', source('Never use a tourniquet.'), Q)
            self.assertTrue(text, report)
            self.assertIn('[1]', text.splitlines()[0])
        text, _ = validate_answer('Do not tie a tight band because it spreads venom.\nNever use a tourniquet [S1].', source('Never use a tourniquet.'), Q)
        self.assertFalse(text)

    def test_fallback_answers_transport_in_all_languages(self):
        for lang, word in [('en', 'stretcher'), ('pt', 'maca'), ('es', 'camilla')]:
            with self.subTest(lang=lang):
                sources = [dict(s, n=i+1) for i,s in enumerate(guidance_sources(plan_query(Q, lang), lang))]
                text, meta = fallback_answer(sources, lang, [])
                self.assertIn(word, text)
                text, report = validate_answer(text.replace('[1]', '[S1]'), sources, Q, lang)
                self.assertTrue(text, report)
                self.assertNotIn('narrow tourniquet', text)
