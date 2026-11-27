"""Isolated regressions from the preserved multilingual evaluation."""
import unittest
from app.answer_validation import validate_answer

Q = 'An unidentified snake bit my leg.'


def check(draft, source):
    return validate_answer(draft + ' [S1].',
                           [dict(n=1, id='reference', kind='kiwix', text=source)], Q)


class QualityFollowupTests(unittest.TestCase):
    def test_spanish_coordinated_prohibition(self):
        for text in ('No uses torniquetes ni ligaduras fuertes',
                     'No utilices torniquetes ni ligaduras fuertes'):
            rendered, report = check(text, 'Do not use a tourniquet or tight band.')
            self.assertTrue(rendered, report)
        for text in ('Usa torniquetes y ligaduras fuertes',
                     'No te preocupes, usa un torniquete',
                     'No uses torniquetes, pero aplica una ligadura fuerte'):
            rendered, report = check(text, 'Do not use a tourniquet or tight band.')
            self.assertFalse(rendered, report)

    def test_positioning_needs_own_evidence(self):
        for text in ('Mantenga el miembro mordido elevado ligeramente (si no hay fracturas)',
                     'Keep the bitten limb elevated', 'Mantenha o membro elevado'):
            rendered, report = check(text, 'Keep the bitten limb still.')
            self.assertFalse(rendered, report)
            self.assertIn('claim_not_supported_by_cited_passage', report['issues'])
        rendered, report = check('Keep the bitten limb elevated', 'Keep the bitten limb elevated.')
        self.assertTrue(rendered, report)
        rendered, report = check('Keep the bitten limb elevated', 'Do not elevate the bitten limb.')
        self.assertFalse(rendered, report)

    def test_unfamiliar_tissue_damage_and_supported_translation(self):
        draft = 'Los torniquetes pueden empeorar el daño tisular'
        rendered, report = check(draft, 'Do not use a tourniquet.')
        self.assertFalse(rendered, report)
        self.assertIn('explanation_not_supported_by_cited_passage', report['issues'])
        rendered, report = check(draft, 'Tourniquets can worsen tissue damage.')
        self.assertTrue(rendered, report)
        rendered, report = check(draft, 'Tourniquets do not worsen tissue damage.')
        self.assertFalse(rendered, report)

    def test_multilingual_circulation_support(self):
        for text in ('Torniquetes podem cortar a circulação',
                     'Los torniquetes pueden restringir la circulación'):
            rendered, report = check(text, 'Tourniquets can cut off blood flow.')
            self.assertTrue(rendered, report)
            rendered, report = check(text, 'Walking accelerates venom spread.')
            self.assertFalse(rendered, report)

    def test_cleaning_region_and_attribution_cannot_be_invented(self):
        cases = (
            ('WHO recommends washing the bite', 'The Red Cross recommends washing the bite.'),
            ('Wash the bite', 'In Brazil, wash the bite.'),
            ('In Australia, wash the bite', 'In Brazil, wash the bite.'),
            ('Do not wash the bite', 'Wash the bite with soap and water.'),
        )
        for draft, evidence in cases:
            with self.subTest(draft=draft):
                rendered, report = check(draft, evidence)
                self.assertFalse(rendered, report)
                self.assertIn('claim_not_supported_by_cited_passage', report['issues'])
        for draft, evidence in (
            ('In Brazil, wash the bite', 'In Brazil, wash the bite.'),
            ('WHO recommends washing the bite', 'WHO recommends washing the bite.'),
            ('Lave a picada', 'Wash the bite.'),
        ):
            rendered, report = check(draft, evidence)
            self.assertTrue(rendered, report)

    def test_species_conclusion_reversal_is_detected_independently(self):
        evidence = ('Tourniquets have been found completely ineffective in the treatment of '
                    'Crotalus durissus bites, but some positive results have been seen with '
                    'properly applied tourniquets for cobra venom in the Philippines.')
        for draft in ('Tourniquets are effective for Crotalus bites',
                      'Torniquetes são eficazes para Crotalus',
                      'Los torniquetes son eficaces para Crotalus'):
            rendered, report = check(draft, evidence)
            self.assertFalse(rendered, report)
            self.assertIn('explanation_not_supported_by_cited_passage', report['issues'])
        draft = ('Não há evidências convincentes de que torniquetes sejam ferramentas eficazes '
                 'de primeiros socorros, exceto em cenários específicos como Crotalus no Brasil')
        rendered, report = check(draft, evidence)
        self.assertFalse(rendered, report)
        self.assertIn('explanation_not_supported_by_cited_passage', report['issues'])
        for draft in ('Tourniquets are ineffective for Crotalus bites',
                      'Torniquetes são ineficazes para Crotalus'):
            rendered, report = check(draft, evidence)
            self.assertTrue(rendered, report)

    def test_positioning_does_not_confuse_raise_alarm_or_drop_conditions(self):
        rendered, report = check('Keep the leg still and raise the alarm', 'Keep the leg still and get help.')
        self.assertTrue(rendered, report)
        rendered, report = check('Elevate the leg', 'Elevate the leg only if instructed by a clinician.')
        self.assertFalse(rendered, report)
        rendered, report = check('Keep the limb elevated if no fractures', 'Keep the limb elevated.')
        self.assertFalse(rendered, report)

    def test_pronoun_explanations_cannot_escape_their_subject(self):
        for draft in ('Esto puede empeorar el daño tisular',
                      'Não use torniquetes. Essa prática pode causar necrose'):
            rendered, report = check(draft, 'Do not use a tourniquet.')
            self.assertFalse(rendered, report)
            self.assertIn('explanation_not_supported_by_cited_passage', report['issues'])

    def test_clean_water_is_not_a_wound_cleaning_instruction(self):
        # Descriptive water quality must not invent a second action family.
        from app.claim_validation import RULES, _matches
        rule = next(rule for rule in RULES if rule.name == 'snake_cleaning')
        self.assertEqual(_matches(rule, 'use a clean cloth to support the limb'), [])
        self.assertEqual(_matches(rule, 'clean water is available'), [])

    def test_other_positioning_cannot_borrow_elevation_or_negated_evidence(self):
        for draft in ('Mantenga el miembro en posición vertical o con la muñeca flexionada',
                      'Keep the wrist flexed', 'Keep the leg in a vertical position'):
            rendered, report = check(draft, 'Keep the limb elevated.')
            self.assertFalse(rendered, report)
            self.assertIn('claim_not_supported_by_cited_passage', report['issues'])
        rendered, report = check('Keep the limb elevated', 'Do not keep the limb elevated.')
        self.assertFalse(rendered, report)
        rendered, report = check('Keep the wrist flexed', 'Keep the wrist flexed.')
        self.assertTrue(rendered, report)

    def test_dehydration_fallback_keeps_urgent_help_when_recipe_is_withheld(self):
        from app.engine import Engine
        from app.guidance import guidance_sources
        from app.query_planner import plan_query
        questions = {
            'en': 'My child has diarrhea, is very sleepy and has not urinated for ten hours.',
            'pt': 'Meu filho tem diarreia, está muito sonolento e não urina há dez horas.',
            'es': 'Mi hijo tiene diarrea, está muy somnoliento y no ha orinado en diez horas.',
        }
        for lang, question in questions.items():
            with self.subTest(lang=lang):
                sources = [dict(s, n=i+1) for i,s in enumerate(guidance_sources(plan_query(question, lang), lang))]
                answer, _, meta = Engine._fallback(sources, lang, [], question, [])
                self.assertTrue(answer, meta)
                self.assertIn('dehydration-escalation', ' '.join(meta['used_source_ids']))

    def test_dehydration_warning_cannot_support_a_renal_failure_diagnosis(self):
        for text in ('No urine is a clear sign of kidney failure',
                     'Não urinar é sinal claro de insuficiência renal',
                     'No ha orinado: señal clara de fallo renal'):
            rendered, report = validate_answer(text + ' [S1].',
                [dict(n=1,id='dehydration-warning',kind='kit',text='Seek urgent help for reduced urine and unusual sleepiness.')],
                'My child has diarrhea and dehydration.')
            self.assertFalse(rendered, report)
            self.assertIn('claim_not_supported_by_cited_passage', report['issues'])
        supported = 'Renal failure requires medical assessment'
        rendered, report = validate_answer(supported + ' [S1].',
            [dict(n=1,id='renal-reference',kind='kit',text=supported)],
            'What are complications of dehydration?')
        self.assertTrue(rendered, report)
