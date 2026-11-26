"""Known consequential claims need their own applicable cited evidence."""
import unittest
import json
from pathlib import Path
import re

from app.answer_validation import validate_answer


def evidence(text, n=1, **kw):
    return dict(n=n, id=f'evidence-{n}', kind='kiwix', doc_title='First aid',
                section='Procedure', text=text, **kw)


class ClaimValidationTests(unittest.TestCase):
    def check(self, answer, source, question, issue=None, lang='en'):
        sources = source if isinstance(source, list) else [evidence(source)]
        rendered, report = validate_answer(answer, sources, question, lang)
        if issue:
            self.assertEqual(rendered, '')
            self.assertIn(issue, report['issues'])
        else:
            self.assertTrue(rendered, report)
        return report

    def test_cooking_fire_routing_enables_guards_for_captured_answer(self):
        path = Path(__file__).parent / 'evals/emergency_advice/baselines/repeated-2026-11-26/final-development.json'
        case = next(c for c in json.loads(path.read_text(encoding='utf-8'))['results']
                    if c['id'] == 'fire_extinguisher')
        request = case['request']
        answer = re.sub(r'\[(\d+)\]', r'[S\1]', case['answer'])
        self.check(answer, case['sources'], request['q'], 'extinguisher_conditions_missing')

    def test_captured_final_action_failures(self):
        path = Path(__file__).parent / 'fixtures/retrieval/final-action-failures.json'
        for case in json.loads(path.read_text(encoding='utf-8')):
            with self.subTest(case=case['id']):
                self.check(re.sub(r'\[(\d+)\]', r'[S\1]', case['answer']),
                           case['sources'], case['request']['q'], case['issue'],
                           case['request']['lang'])

    def test_embedded_object_removal_boundaries(self):
        for lang, ban, affirmative, exception, question in (
            ('en', 'Do not remove embedded objects', 'Remove embedded objects',
             'unless they prevent pressure', 'A wound is bleeding'),
            ('pt', 'Não retire objetos encravados', 'Retire objetos encravados',
             'a menos que impeçam a pressão', 'Ferida sangrando'),
            ('es', 'No retire objetos incrustados', 'Retire objetos incrustados',
             'a menos que impidan la presión', 'Herida sangrando')):
            for answer in (affirmative, ban + ' ' + exception):
                with self.subTest(answer=answer):
                    self.check(answer + ' [S1].', ban, question,
                               'embedded_object_removal_unsafe', lang)
            self.check(ban + ' [S1].', ban, question, lang=lang)
            self.check(ban + ' [S1].', affirmative, question,
                       'claim_not_supported_by_cited_passage', lang)

    def test_generator_shutdown_and_return_boundaries(self):
        for lang, question, stop, ban, enter, no_entry, cleared in (
            ('en', 'Generator in garage, carbon monoxide poisoning',
             'Turn off the generator', 'Do not turn off the generator',
             'Re-enter the garage', 'Do not re-enter the garage',
             'only after trained personnel declare the area safe'),
            ('pt', 'Gerador na garagem causa monóxido de carbono',
             'Desligue o gerador', 'Não desligue o gerador',
             'Volte à garagem', 'Não volte à garagem',
             'somente após profissionais treinados liberarem o local'),
            ('es', 'Generador en garaje causa monóxido de carbono',
             'Apague el generador', 'No apague el generador',
             'Regrese al garaje', 'No regrese al garaje',
             'solo después de que profesionales capacitados declaren segura la zona')):
            with self.subTest(lang=lang):
                self.check(stop + ' [S1].', ban, question,
                           'generator_shutdown_condition_missing', lang)
                self.check(enter + ' [S1].', no_entry, question,
                           'generator_reentry_condition_missing', lang)
                self.check(ban + ' [S1].', ban, question, lang=lang)
                self.check(no_entry + ' [S1].', no_entry, question, lang=lang)
                safe = enter + ' ' + cleared
                self.check(safe + ' [S1].', safe, question, lang=lang)
                self.check(safe + ' [S1].', enter, question,
                           'claim_not_supported_by_cited_passage', lang)
                self.check(stop + ' [S1]. ' + safe + ' [S1].', safe, question,
                           'generator_shutdown_condition_missing', lang)

    def test_generator_shutdown_nested_prohibitions_remain_valid(self):
        for lang, answer, question in (
            ('en', 'Do not return to turn off the generator', 'Carbon monoxide poisoning'),
            ('pt', 'Não volte para desligar equipamento', 'Monóxido de carbono'),
            ('es', 'No regrese para apagar el generador', 'Monóxido de carbono')):
            with self.subTest(lang=lang):
                self.check(answer + ' [S1].', answer, question, lang=lang)
                self.check(answer + ' unless everyone is outside [S1].', answer, question,
                           'generator_reentry_condition_missing', lang)

    def test_unrelated_return_instruction_is_not_generator_reentry(self):
        self.check('Return the phone to its owner [S1].', 'Return the phone to its owner.',
                   'Carbon monoxide poisoning')

    def test_generator_clearance_cannot_be_borrowed_from_another_action(self):
        answer = ('Re-enter the garage; call emergency services only after trained personnel '
                  'declare the area safe [S1].')
        self.check(answer, answer, 'Carbon monoxide poisoning',
                   'generator_reentry_condition_missing')

    def test_embedded_conditional_source_cannot_support_unconditional_ban(self):
        self.check('Do not remove embedded objects [S1].',
                   'Do not remove embedded objects unless they prevent pressure.',
                   'A wound is bleeding', 'claim_not_supported_by_cited_passage')

    def test_generator_conditional_prohibitions_need_professional_clearance(self):
        for lang, bad, good in (
            ('en', 'Do not re-enter the garage until everyone is outside',
             'Do not re-enter the garage until trained personnel declare the area safe'),
            ('pt', 'Não volte à garagem até todos estarem fora',
             'Não volte à garagem até profissionais treinados liberarem o local'),
            ('es', 'No regrese al garaje hasta que todos estén fuera',
             'No regrese al garaje hasta que profesionales capacitados declaren segura la zona')):
            with self.subTest(lang=lang):
                self.check(bad + ' [S1].', good, 'Carbon monoxide poisoning',
                           'generator_reentry_condition_missing', lang)
                self.check(good + ' [S1].', good, 'Carbon monoxide poisoning', lang=lang)

    def test_generator_clearance_cannot_offer_weaker_alternative(self):
        question = 'Generator in the garage caused headaches; can I go back?'
        for lang, safe, alternative in (
            ('en', 'Re-enter the garage only after trained personnel declare the area safe',
             'or if the door is open'),
            ('pt', 'Volte à garagem somente após profissionais treinados liberarem o local',
             'ou se a porta estiver aberta'),
            ('es', 'Regrese al garaje solo después de que profesionales capacitados declaren segura la zona',
             'o si la puerta está abierta')):
            bad = safe + ' ' + alternative
            with self.subTest(lang=lang):
                self.check(bad + ' [S1].', safe + '.', question,
                           'generator_reentry_condition_missing', lang)
                self.check(safe + ' [S1].', bad + '.', question,
                           'claim_not_supported_by_cited_passage', lang)
                self.check(safe + ' [S1].', safe + '.', question, lang=lang)

    def test_visible_airway_object_is_not_an_embedded_wound_object(self):
        answer = 'Remove a clearly visible foreign object from the mouth [S1].'
        source = 'Remove a clearly visible foreign object from the mouth.'
        report = self.check(answer, source, 'My 8-month-old infant is choking')
        self.assertNotIn('embedded_object',
                         [claim['rule'] for claim in report['claim_checks']['claims']])

    def test_cpr_continuation_cannot_stop_at_mere_arrival(self):
        for lang, question, bad, good in (
            ('en', 'My father is unresponsive and only gasping',
             'Continue compressions until medical help or an AED arrives',
             'Continue compressions until trained responders take over, normal breathing returns, you are exhausted or the scene is unsafe'),
            ('pt', 'Meu pai está inconsciente e não respira normalmente',
             'Continue as compressões até chegar ajuda médica ou um DEA',
             'Continue as compressões até respirar normalmente, alguém assumir, ficar exausto ou o local ficar inseguro'),
            ('es', 'Mi padre no responde y solo jadea',
             'Continúe las compresiones hasta que llegue ayuda médica o un DEA',
             'Continúe las compresiones hasta que respire normalmente, alguien lo releve, se agote o el lugar sea inseguro')):
            with self.subTest(lang=lang):
                self.check(bad + ' [S1].', good, question, 'cpr_arrival_stop_unsafe', lang)
                self.check(good + ' [S1].', good, question, lang=lang)
                self.check(good + ' [S1].', bad, question,
                           'claim_not_supported_by_cited_passage', lang)
        instruction = 'Pause compressions only when the AED tells you to, then resume immediately'
        self.check(instruction + ' [S1].', instruction,
                   'My father is unresponsive and only gasping')

    def test_cpr_arrival_branch_cannot_borrow_takeover_from_another_bullet(self):
        safe = ('Continue until:\n* Normal breathing returns.\n'
                '* Trained responders arrive and take over.\n'
                '* You are exhausted or the scene is unsafe [S1].')
        question = 'My father is unresponsive and only gasping'
        self.check(safe, safe, question)
        bad = safe.replace('* You are exhausted', '* An AED arrives.\n* You are exhausted')
        self.check(bad, safe, question, 'cpr_arrival_stop_unsafe')
        self.check(safe, bad, question, 'claim_not_supported_by_cited_passage')
        prohibition = 'Do not stop compressions merely because help arrives'
        self.check(prohibition + ' [S1].', prohibition, question)
        separate = safe + '\n### Equipment\nAn AED arrives later.'
        self.check(separate, safe, question)

    def test_each_cpr_arrival_requires_its_own_takeover_condition(self):
        question = 'My father is unresponsive and gasping.'
        for lang, safe, alternative in (
            ('en', 'Continue compressions until trained responders arrive and take over',
             'or an AED arrives'),
            ('pt', 'Continue as compressões até a ajuda chegar e assumir',
             'ou um DEA chegar'),
            ('es', 'Continúe las compresiones hasta que el socorrista llegue y se haga cargo',
             'o llegue un DEA')):
            bad = safe + ' ' + alternative
            with self.subTest(lang=lang):
                self.check(bad + ' [S1].', safe + '.', question,
                           'cpr_arrival_stop_unsafe', lang)
                self.check(safe + ' [S1].', bad + '.', question,
                           'claim_not_supported_by_cited_passage', lang)
                self.check(safe + ' [S1].', safe + '.', question, lang=lang)

    def test_generator_ventilation_is_not_an_indoor_use_exception(self):
        source = 'Never use a generator indoors or in a garage, even with open windows.'
        question = 'Gasoline generator in garage, headaches and nausea; add a fan?'
        for answer in (
                'Use a generator indoors with professional ventilation [S1].',
                'The generator must never be used indoors without professional ventilation [S1].',
                'Do not use a generator in the garage unless the door is open [S1].',
                'Do not use a generator indoors if ventilation is inadequate [S1].',
                'Never use a generator in the garage when the door is closed [S1].'):
            with self.subTest(answer=answer):
                self.check(answer, source, question, 'generator_indoor_use_unsafe')
        self.check(source + ' [S1]', source, question)
        unconditional = 'Never use a generator indoors, with or without ventilation.'
        self.check(unconditional + ' [S1]', unconditional, question)
        even_if = 'Never use a generator indoors, even if the windows are open.'
        self.check(even_if + ' [S1]', even_if, question)

    def test_food_smell_cannot_establish_safety_after_outage(self):
        source = 'Never judge food safety by appearance, smell or taste.'
        question = 'The refrigerator has been without power for 10 hours. Can we eat the chicken and milk?'
        for answer in (
                'Re-evaluate based on appearance and smell before consumption [S1].',
                'Judge food safety by smell [S1].',
                'Eat it if it smells normal [S1].'):
            with self.subTest(answer=answer):
                self.check(answer, source, question, 'food_sensory_safety_unsupported')
        self.check(source + ' [S1]', source, question)

    def test_captured_candidate_hazards_are_rejected(self):
        path = Path(__file__).parent / 'fixtures/retrieval/candidate-unsafe-claims.json'
        for case in json.loads(path.read_text(encoding='utf-8')):
            with self.subTest(case=case['id']):
                answer = re.sub(r'\[(\d+)\]', r'[S\1]', case['answer'])
                issue = ('generator_indoor_use_unsafe' if case['id'] == 'co'
                         else 'food_sensory_safety_unsupported')
                self.check(answer, case['sources'], case['request']['q'], issue)

    def test_translated_generator_and_food_boundaries(self):
        for lang, question, prohibited, allowed in (
                ('pt', 'Gerador na garagem causa monóxido de carbono',
                 'Use o gerador na garagem sem ventilação.',
                 'Nunca use o gerador na garagem.'),
                ('es', 'Generador en garaje causa monóxido de carbono',
                 'Use el generador en el garaje con ventilación.',
                 'Nunca use el generador en el garaje.')):
            self.check(prohibited + ' [S1]', allowed, question,
                       'generator_indoor_use_unsafe', lang)
            self.check(allowed + ' [S1]', allowed, question, lang=lang)
        for lang, question, prohibited, allowed in (
                ('pt', 'Segurança alimentar após falta de energia',
                 'Julgue a segurança pelo cheiro.', 'Nunca julgue a segurança pelo cheiro.'),
                ('es', 'Seguridad alimentaria sin electricidad',
                 'Juzgue la seguridad por el olor.', 'Nunca juzgue la seguridad por el olor.')):
            self.check(prohibited + ' [S1]', allowed, question,
                       'food_sensory_safety_unsupported', lang)
            self.check(allowed + ' [S1]', allowed, question, lang=lang)

    def test_versioned_eval_failures_remain_rejected_with_valid_citation_ids(self):
        path = Path(__file__).parent / 'evals/emergency_advice/baselines/current.json'
        cases = json.loads(path.read_text(encoding='utf-8'))['results']
        expected = {'burn':'burn_clothing_condition_missing',
                    'snake':'snake_compression_scope_missing',
                    'flood':'flood_entrapment_condition_missing',
                    'allergy_followup':'injector_device_scope_missing',
                    'diabetes':'claim_not_supported_by_cited_passage',
                    'water_chemical':'claim_not_supported_by_cited_passage',
                    'grease_fire':'grease_fire_equipment_unsupported'}
        for case in cases:
            if case['id'] not in expected:
                continue
            with self.subTest(case=case['id']):
                request = case['request']
                answer = re.sub(r'\[(\d+)\]', r'[S\1]', case['answer'])
                rendered, report = validate_answer(answer, case['sources'], request['q'],
                                                   request['lang'], request['history'])
                self.assertEqual(rendered, '')
                self.assertIn(expected[case['id']], report['issues'])
                self.assertNotIn('citation_not_supplied', report['issues'])

    def test_burn_clothing_exception_and_supported_counterpart(self):
        source = 'Remove clothing near the burn, except clothing stuck to the skin.'
        self.check('Remove clothing near the burn [S1].', source, 'Boiling water burned my arm',
                   'burn_clothing_condition_missing')
        self.check('Take off clothing near the burn, but leave anything stuck to skin [S1].',
                   source, 'Boiling water burned my arm')

    def test_following_specific_warning_attaches_but_unrelated_warning_does_not(self):
        source = 'Remove clothing near the burn, except clothing stuck to the skin.'
        self.check('Remove clothing near the burn. Do not remove anything stuck to skin [S1].', source,
                   'My arm is burned')
        self.check('Remove clothing near the burn [S1]. Do not drive through floodwater.', source,
                   'My arm is burned', 'burn_clothing_condition_missing')

    def test_airway_condition_for_heat_immersion(self):
        source = 'For heat stroke, immerse in cool water only while a helper keeps the head above water and monitors breathing.'
        self.check('Immerse him in cold water [S1].', source, 'Heatstroke and unconscious',
                   'immersion_airway_condition_missing')
        self.check('Immerse him in cool water only while a helper keeps his head above water and monitors breathing [S1].',
                   source, 'Heatstroke and unconscious')

    def test_unknown_region_cannot_authorize_snake_compression(self):
        source = 'For Australian snakebite, apply a pressure immobilisation bandage and keep the limb still.'
        answer = 'Apply a pressure immobilisation bandage and keep the limb still [S1].'
        self.check(answer, source, 'A snake bit my ankle', 'snake_compression_scope_missing')
        self.check(answer, source, 'A snake bit my ankle in Australia')

    def test_injector_hold_time_needs_named_device_and_its_own_evidence(self):
        source = 'Use the prescribed epinephrine auto-injector according to its instructions.'
        self.check('Hold the auto-injector in place for 3 seconds [S1].', source,
                   'Anaphylaxis after a bee sting', 'injector_device_scope_missing')
        self.check('Hold the EpiPen auto-injector in place for 3 seconds [S1].',
                   'For EpiPen, hold the auto-injector in place for 3 seconds.',
                   'I have an EpiPen for anaphylaxis')

    def test_flood_waiting_requires_rising_water_exception(self):
        source = 'If trapped in rapidly moving floodwater, stay in the vehicle. If water is rising inside, get onto the roof and call for help.'
        self.check('If already stuck, wait for the water to recede [S1].', source,
                   'Can my SUV cross this flood?', 'flood_entrapment_condition_missing')
        self.check('If trapped in rapidly moving water, stay in the vehicle; if water is rising inside, get onto the roof and call for help [S1].',
                   source, 'Can my SUV cross this flood?')

    def test_grease_fire_foil_and_unsuitable_extinguisher(self):
        self.check('Cover the burning pan with aluminum foil [S1].',
                   'For a small pan fire, slide a lid over it only if safe.', 'A pan of cooking oil is on fire',
                   'grease_fire_equipment_unsupported')
        self.check('Use a Class B extinguisher [S1].', 'Use an extinguisher rated for cooking oil only if trained, with a clear escape route and a small contained fire.',
                   'A pan of cooking oil is on fire', 'extinguisher_conditions_missing')

    def test_definition_cannot_support_cpr_instruction(self):
        self.check('If unresponsive and not breathing normally, start CPR [S1].',
                   'Hypoglycemia is low blood sugar.', 'My husband is unconscious after insulin',
                   'claim_not_supported_by_cited_passage')

    def test_only_cited_passage_can_support_instruction(self):
        sources = [evidence('Hypoglycemia is low blood sugar.'),
                   evidence('If awake and able to swallow safely, give oral glucose.', 2)]
        self.check('If awake and able to swallow safely, give oral glucose [S1].', sources,
                   'Low blood sugar', 'claim_not_supported_by_cited_passage')
        self.check('If awake and able to swallow safely, give oral glucose [S2].', sources,
                   'Low blood sugar')

    def test_source_polarity_and_condition_are_not_ignored(self):
        self.check('If awake and able to swallow safely, give oral glucose [S1].',
                   'Do not give oral glucose.', 'Low blood sugar', 'claim_not_supported_by_cited_passage')
        self.check('If unresponsive and not breathing normally, start CPR [S1].',
                   'If unconscious, start CPR.', 'Carbon monoxide poisoning',
                   'claim_not_supported_by_cited_passage')

    def test_different_medication_does_not_support_glucose(self):
        self.check('If awake and able to swallow safely, give oral glucose [S1].',
                   'If awake and able to swallow safely, give an antihistamine tablet.',
                   'Hypoglycemia', 'claim_not_supported_by_cited_passage')

    def test_source_or_condition_does_not_support_safe_oral_rule(self):
        self.check('If awake and able to swallow safely, give glucose [S1].',
                   'If awake or able to swallow safely, give glucose.',
                   'Hypoglycemia', 'claim_not_supported_by_cited_passage')

    def test_water_claim_requires_chemical_evidence(self):
        self.check('Boiling does not remove fuel or toxic chemicals [S1].',
                   'Boiling kills germs in water.', 'My well smells of gasoline',
                   'claim_not_supported_by_cited_passage')
        self.check('Boiling cannot make water containing fuel safe [S1].',
                   'Water containing fuel or toxic chemicals cannot be made safe by boiling.',
                   'My well smells of gasoline')

    def test_quantity_must_belong_to_same_cited_action(self):
        self.check('Cool the burn under running water for 10 minutes [S1].',
                   'Cool the burn under running water for 20 minutes. Rest for 10 minutes.',
                   'My hand is burned', 'claim_quantity_not_supported')
        self.check('Cool the burn with running water for 20 minutes [S1].',
                   'Cool the burn under running water for 20 minutes.', 'My hand is burned')

    def test_translation_conditions(self):
        for lang, question, bad, good in (
            ('pt', 'Queimadura no braço', 'Retire a roupa perto da queimadura [S1].',
             'Retire a roupa perto da queimadura, mas não retire roupa grudada na pele [S1].'),
            ('es', 'Quemadura en el brazo', 'Retire la ropa cerca de la quemadura [S1].',
             'Retire la ropa cerca de la quemadura, pero no retire ropa pegada a la piel [S1].')):
            with self.subTest(lang=lang):
                self.check(bad, good, question, 'burn_clothing_condition_missing', lang)
                self.check(good, good, question, lang=lang)

    def test_unknown_explanations_are_not_certified(self):
        report = self.check('A general explanation [S1].', 'A general explanation.', 'First aid')
        self.assertEqual(report['claim_support'], 'not_verified')
        self.assertEqual(report['claim_checks']['coverage'], 'known_patterns_only')
        self.assertEqual(report['claim_checks']['claims'], [])

    def test_diagnostics_never_contain_rejected_draft(self):
        answer = 'UNRELEASED. Remove clothing near the burn [S1].'
        report = self.check(answer, 'Remove clothing except anything stuck to skin.', 'A burn',
                            'burn_clothing_condition_missing')
        self.assertNotIn('UNRELEASED', str(report))

    def test_reviewed_scope_polarity_object_and_quantity_counterexamples(self):
        cases = [
            ('Remove clothing stuck to the burn; do not remove jewelry [S1].',
             'Remove clothing near the burn except clothing stuck to skin.', 'A burn'),
            ('Hold the Jext in place for 3 seconds [S1].',
             'For EpiPen, hold the injector for 3 seconds.', 'I have an EpiPen for anaphylaxis'),
            ('If awake and able to swallow safely, give 150 grams of oral glucose [S1].',
             'If awake and able to swallow safely, give 15 grams of oral glucose.', 'Hypoglycemia'),
            ('Cool the burn with running water for 10 minutes [S1].',
             'Cool the burn with running water for 20 minutes and rest for 10 minutes.', 'My arm is burned'),
            ('Immerse him while a helper keeps his head under water, not above water, and monitors breathing [S1].',
             'Immerse in cool water while a helper keeps the head above water and monitors breathing.', 'Heatstroke and unconscious'),
            ('If safe, cover the burning pan with a paper towel [S1].',
             'If safe, cover the burning pan with a metal lid.', 'A pan of cooking oil is on fire'),
            ('Stay inside the vehicle; if water is rising inside, do not get onto the roof [S1].',
             'Stay in the vehicle; if water is rising inside, get onto the roof.', 'Can my SUV cross this flood?'),
            ('If unresponsive and not breathing normally, start CPR [S1].',
             'For infants only, if unresponsive and not breathing normally, start CPR.', 'An adult is unresponsive and not breathing normally'),
            ('Apply a pressure immobilisation bandage [S1].',
             'For Australian snakebite, apply a pressure immobilisation bandage.', 'A snake bit me; I am not in Australia'),
            ('If not awake and able to swallow safely, give glucose [S1].',
             'If awake and able to swallow safely, give glucose.', 'Hypoglycemia'),
            ('Se consciente e consegue engolir, dê 150 gramas de glicose [S1].',
             'Se consciente e consegue engolir, dê 15 gramas de glicose.', 'Hipoglicemia'),
        ]
        for answer, source, question in cases:
            with self.subTest(answer=answer):
                rendered, report = validate_answer(answer, [evidence(source)], question)
                self.assertEqual(rendered, '', report)

    def test_decimal_doses_remain_in_the_claim_sentence(self):
        source = 'If awake and able to swallow safely, give 15.0 grams of oral glucose.'
        self.check('If awake and able to swallow safely, give 15.5 grams of oral glucose [S1].',
                   source, 'Hypoglycemia', 'claim_quantity_not_supported')
        report = self.check('If awake and able to swallow safely, give 15.0 grams of oral glucose [S1].',
                            source, 'Hypoglycemia')
        self.assertEqual(len(report['claim_checks']['claims']), 1)

    def test_repeat_doses_are_checked_separately_from_initial_dose(self):
        source = 'If awake and able to swallow safely, give 15 grams of glucose and repeat 15 grams if needed.'
        self.check('If awake and able to swallow safely, give 15 grams of glucose and repeat 150 grams immediately [S1].',
                   source, 'Hypoglycemia', 'claim_quantity_not_supported')
        self.check('If awake and able to swallow safely, give 15 grams of glucose and repeat 15 grams if needed [S1].',
                   source, 'Hypoglycemia')
        self.check('If awake and able to swallow safely, give 15 grams of glucose and repeat 30 grams if needed [S1].',
                   'If awake and able to swallow safely, give 30 grams of glucose and repeat 15 grams if needed.',
                   'Hypoglycemia', 'claim_quantity_not_supported')

    def test_negative_equipment_and_swallow_conditions_do_not_support_actions(self):
        source = 'Use an extinguisher suitable for cooking oil only if trained, with a clear escape route and a small contained fire.'
        self.check('Use an extinguisher not suitable for cooking oil even if not trained, with no escape route and a small fire [S1].',
                   source, 'A pan of cooking oil is on fire', 'extinguisher_conditions_missing')
        self.check(source[:-1] + ' [S1].', source, 'A pan of cooking oil is on fire')
        self.check('If awake and able to swallow safely, give glucose [S1].',
                   'If awake but not able to swallow safely, give glucose.',
                   'Hypoglycemia', 'claim_not_supported_by_cited_passage')

    def test_reversed_burn_exception_is_rejected(self):
        source = 'Remove clothing except anything stuck to the skin.'
        self.check('Remove clothing, except anything not stuck to the skin [S1].', source,
                   'A burn', 'burn_clothing_condition_missing')

    def test_species_restricted_evidence_cannot_authorize_unknown_species(self):
        self.check('Apply a pressure immobilisation bandage [S1].',
                   'For Australian snakebite, apply a pressure immobilisation bandage only for species X.',
                   'A snake bit me in Australia; species unknown', 'claim_not_supported_by_cited_passage')

    def test_cpr_prohibition_has_negative_polarity(self):
        report = self.check('Do not start CPR [S1].', 'Do not start CPR.',
                            'The adult is awake and breathing normally')
        self.assertFalse(report['claim_checks']['claims'][0]['positive'])
        self.check('Do not start CPR [S1].',
                   'If unresponsive and not breathing normally, start CPR.',
                   'The adult is awake and breathing normally', 'claim_not_supported_by_cited_passage')

    def test_semicolon_keeps_repeat_dose_association(self):
        self.check('If awake and able to swallow safely, give 15 grams of glucose; repeat 30 grams if needed [S1].',
                   'If awake and able to swallow safely, give 30 grams of glucose; repeat 15 grams if needed.',
                   'Hypoglycemia', 'claim_quantity_not_supported')

    def test_each_extinguisher_prerequisite_rejects_its_explicit_negation(self):
        source = 'Use an extinguisher suitable for cooking oil only if trained, with a clear escape route and a small contained fire.'
        for positive, negative in [('suitable', 'not suitable'), ('trained', 'not trained'),
                                   ('a clear escape route', 'no escape route'), ('small contained', 'not small or contained')]:
            with self.subTest(negative=negative):
                bad = source.replace(positive, negative)
                self.check(bad[:-1] + ' [S1].', source, 'A pan of cooking oil is on fire',
                           'extinguisher_conditions_missing')
                self.check(source[:-1] + ' [S1].', bad, 'A pan of cooking oil is on fire',
                           'claim_not_supported_by_cited_passage')

    def test_decimal_comma_is_checked_in_portuguese(self):
        source = 'Se consciente e consegue engolir, dê 15,0 gramas de glicose.'
        self.check('Se consciente e consegue engolir, dê 15,5 gramas de glicose [S1].',
                   source, 'Hipoglicemia', 'claim_quantity_not_supported', 'pt')
        self.check(source[:-1] + ' [S1].', source, 'Hipoglicemia', lang='pt')

    def test_cpr_prohibitions_preserve_patient_scope(self):
        source = 'Do not start CPR if the person is awake and breathing normally.'
        self.check('Do not start CPR if unresponsive and not breathing normally [S1].',
                   source, 'The adult is unresponsive and not breathing normally',
                   'claim_not_supported_by_cited_passage')
        self.check(source[:-1] + ' [S1].', source,
                   'The adult is awake and breathing normally')
        self.check('Do not start CPR [S1].', source,
                   'The adult is awake and breathing normally')
        self.check('Do not start CPR [S1].', source,
                   'The adult is unresponsive and not breathing normally',
                   'claim_not_supported_by_cited_passage')

    def test_injector_quantity_stays_with_its_device(self):
        for separator in ('; ', ', and '):
            with self.subTest(separator=separator):
                source = 'For EpiPen, hold for 3 seconds' + separator + 'for Jext, hold for 10 seconds.'
                self.check('Hold the EpiPen in place for 10 seconds [S1].', source,
                           'I have an EpiPen for anaphylaxis', 'claim_quantity_not_supported')
                self.check('Hold the EpiPen in place for 3 seconds [S1].', source,
                           'I have an EpiPen for anaphylaxis')

    def test_repeat_dose_preserves_interval_and_condition(self):
        prefix = 'If awake and able to swallow safely, give 15 grams of glucose and '
        source = prefix + 'repeat 15 grams after 15 minutes if needed.'
        for repeat in ('repeat 15 grams immediately', 'repeat 15 grams if needed',
                       'repeat 15 grams after 15 minutes'):
            with self.subTest(repeat=repeat):
                self.check(prefix + repeat + ' [S1].', source, 'Hypoglycemia',
                           'claim_not_supported_by_cited_passage')
        self.check(source[:-1] + ' [S1].', source, 'Hypoglycemia')
        self.check('If awake and able to swallow safely, give 15 grams of glucose [S1].',
                   source, 'Hypoglycemia')

    def test_chemical_claim_polarity_belongs_to_disinfection_clause(self):
        source = 'Water containing fuel cannot be made safe by boiling.'
        self.check('Boil water containing fuel to make it safe; do not worry [S1].',
                   source, 'My well smells of gasoline', 'claim_not_supported_by_cited_passage')
        self.check('Boiling cannot make water containing fuel safe; do not worry [S1].',
                   source, 'My well smells of gasoline')
        self.check('Do not worry; boiling cannot make water containing fuel safe [S1].',
                   source, 'My well smells of gasoline')

    def test_negative_oral_claim_preserves_swallowing_scope(self):
        source = 'Do not give glucose if awake but unable to swallow safely.'
        self.check('Do not give glucose if awake and able to swallow safely [S1].',
                   source, 'Hypoglycemia', 'claim_not_supported_by_cited_passage')
        self.check(source[:-1] + ' [S1].', source, 'Hypoglycemia')

    def test_cpr_source_cannot_negate_required_unresponsiveness(self):
        self.check('If unresponsive and not breathing normally, start CPR [S1].',
                   'If not unresponsive and not breathing normally, start CPR.',
                   'An adult is unconscious and not breathing normally',
                   'claim_not_supported_by_cited_passage')
