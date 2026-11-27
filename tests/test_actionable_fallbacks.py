"""Useful alternatives and preserved conditions from the remaining quality findings."""
import unittest
from unittest.mock import patch
from app.engine import Engine
from app.guidance import guidance_sources, fallback_answer
from app.query_planner import plan_query
from app.source_policy import evaluate_conflicts
from app.answer_validation import validate_answer


def sources(question, lang='en'):
    return [dict(s, n=i) for i, s in enumerate(guidance_sources(plan_query(question, lang), lang), 1)]


class ActionableFallbackTests(unittest.TestCase):
    def test_water_quantity_conflict_preserves_only_independent_supply(self):
        disputed = [dict(id='a', text='Add 2 drops of bleach per liter.'),
                    dict(id='b', text='Add 4 drops of bleach per liter.')]
        conflicts = evaluate_conflicts(disputed, ['water_disinfection'])
        for lang in ('en', 'pt', 'es'):
            admitted = sources('How much bleach should I add to drinking water?', lang)
            text, meta = fallback_answer(admitted, lang, conflicts)
            self.assertTrue(text, meta)
            self.assertTrue(any('water-safe-supply' in sid for sid in meta['used_source_ids']))
            self.assertFalse(any('water-product' in sid for sid in meta['used_source_ids']))
            rendered, _, result = Engine._fallback(admitted, lang, conflicts, 'How much bleach for drinking water?', [])
            self.assertTrue(rendered, result)

    def test_unknown_conflict_and_policy_error_remain_closed(self):
        admitted = sources('How much bleach for drinking water?')
        for conflict in ({'resolution':'unresolved','topic':'water_disinfection'},
                         {'resolution':'unresolved','topic':'unspecified'},
                         {'resolution':'policy_error'}):
            self.assertFalse(fallback_answer(admitted, 'en', [conflict])[0])

    def test_disputed_supply_itself_cannot_be_reintroduced(self):
        admitted = sources('How much bleach for drinking water?')
        supply = next(s for s in admitted if s['guidance_unit'] == 'water-safe-supply')
        conflict = {'resolution':'unresolved','topic':'water_disinfection',
                    'action_scope':['water_treatment'], 'source_ids':[supply['id']]}
        self.assertFalse(fallback_answer([supply], 'en', [conflict])[0])

    def test_lone_snakebite_in_all_languages_has_help_without_a_phone(self):
        for lang, terms in [('en', ('whistle','only option')), ('pt', ('apito','única opção')), ('es', ('silbato','única opción'))]:
            engine = Engine({'kiwix_enabled':False})
            with patch.object(engine, 'llm', return_value=None):
                text, _, done = engine.answer_text('An unknown snake bit my leg. I am alone without phone service.', lang=lang, use_kiwix=False)
            self.assertEqual(done['mode'], 'fallback', done)
            for term in terms:
                self.assertIn(term, text.lower())

    def test_tourniquet_catalog_does_not_invent_training_requirement(self):
        for lang in ('en','pt','es'):
            admitted = sources('Life-threatening bleeding from a leg. I am untrained and have a commercial tourniquet.',lang)
            unit = next(s for s in admitted if s['guidance_unit']=='bleeding-tourniquet')
            self.assertNotIn('trained',unit['prerequisites'])
            text, _, report = Engine._fallback(admitted,lang,[],'Life-threatening bleeding from a leg. I am untrained and have a commercial tourniquet.',[])
            self.assertTrue(text,report)

    def test_tourniquet_cannot_borrow_training_restricted_evidence(self):
        draft = 'For life-threatening arm or leg bleeding, use a commercial tourniquet if available [S1].'
        restricted = 'For life-threatening arm or leg bleeding, use a commercial tourniquet if available and you are trained.'
        question = 'Severe bleeding from a leg. I have no training.'
        text, result = validate_answer(draft,[dict(n=1,text=restricted)],question)
        self.assertFalse(text,result)
        text, result = validate_answer(draft,[dict(n=1,text=draft)],question)
        self.assertTrue(text,result)
        for unsafe in ('Use a tourniquet [S1].','For minor bleeding from an arm, use a tourniquet if available [S1].'):
            self.assertFalse(validate_answer(unsafe,[dict(n=1,text=draft)],question)[0])

    def test_tourniquet_negated_conditions_and_adjacent_training(self):
        good = 'For life-threatening arm or leg bleeding, use a commercial tourniquet if available [S1].'
        for restriction in (' Use it only if trained.', ' Only trained responders should apply the tourniquet.'):
            self.assertFalse(validate_answer(good,[dict(n=1,text=good+restriction)],'A leg is bleeding.')[0])
        bad = good.replace('life-threatening', 'not life-threatening')
        self.assertFalse(validate_answer(bad,[dict(n=1,text=good)],'A leg is bleeding.')[0])

    def test_lone_movement_cannot_drop_necessity_or_route_conditions(self):
        good = ('If moving to help is your only option, and you can do so safely on a known route, '
                'walk toward help with as little exertion as possible [S1].')
        self.assertTrue(validate_answer(good,[dict(n=1,text=good)],'A snake bit me.')[0])
        for bad in ('Walk toward help [S1].', good.replace('only option','preferred option'),
                    good.replace('safely on a known route', 'on any route')):
            self.assertFalse(validate_answer(bad,[dict(n=1,text=good)],'A snake bit me.')[0])
        paraphrase = 'Only walk toward help as your last option if the route is known and safe [S1].'
        self.assertTrue(validate_answer(paraphrase,[dict(n=1,text=good)],'A snake bit me.')[0])
        for bad in (paraphrase.replace('known and safe','known or safe'),
                    paraphrase.replace('known and safe','known but not safe')):
            self.assertFalse(validate_answer(bad,[dict(n=1,text=good)],'A snake bit me.')[0])

    def test_portuguese_preposition_is_not_an_oral_instruction(self):
        good = 'Use água engarrafada de uma fonte segura para preparar alimentos [S1].'
        self.assertTrue(validate_answer(good,[dict(n=1,text=good)],'Preciso de água potável.','pt')[0])
        bad = 'Dê água ao homem inconsciente [S1].'
        self.assertFalse(validate_answer(bad,[dict(n=1,text=bad)],'O homem está inconsciente.','pt')[0])

    def test_tourniquet_heading_keeps_its_immediate_cited_condition(self):
        condition = 'For life-threatening bleeding from an arm or leg, use a commercial tourniquet if available [S1].'
        answer = '3. **Use a tourniquet:**\n    * ' + condition
        self.assertTrue(validate_answer(answer,[dict(n=1,text=condition)],'A leg is bleeding.')[0])
        bad = answer.replace('life-threatening','minor')
        self.assertFalse(validate_answer(bad,[dict(n=1,text=condition)],'A leg is bleeding.')[0])

    def test_spanish_bleeding_inflection_selects_relevant_guidance(self):
        q = 'Una persona sangra mucho del muslo. No tengo formación médica, pero hay un torniquete comercial y un equipo IV.'
        self.assertIn('bleeding',plan_query(q,'es').topics)
        self.assertIn('bleeding-tourniquet',{s['guidance_unit'] for s in sources(q,'es')})

    def test_invasive_iv_instruction_is_blocked_even_without_a_topic(self):
        for draft in ('Solo intente insertar un catéter IV si ya ha colocado el torniquete [S1].',
                      'Insert an IV after stopping the bleeding [S1].'):
            rendered, report = validate_answer(draft,[dict(n=1,text=draft)],'What should I do?','es')
            self.assertFalse(rendered,report)
            self.assertIn('clinical_drug_administration',report['issues'])
        prohibition = 'No intente insertar una vía IV; deje el acceso invasivo a profesionales capacitados [S1].'
        self.assertTrue(validate_answer(prohibition,[dict(n=1,text=prohibition)],'What should I do?','es')[0])

    def test_spanish_movement_cannot_replace_last_resort_with_worsening(self):
        good = next(s for s in sources('Una serpiente me mordió.','es') if s['guidance_unit']=='snakebite-no-contact')
        bad = 'Si los síntomas empeoran, intente moverse solo hacia el transporte más cercano si la ruta es segura [S1].'
        self.assertFalse(validate_answer(bad,[dict(good,n=1)],'Una serpiente me mordió.','es')[0])

    def test_spanish_tourniquet_placement_needs_procedure_evidence(self):
        bad = 'Coloque el torniquete 2-3 cm por encima de la herida [S1].'
        inventory = 'Botiquín: guantes, solución salina, torniquete comercial, manta térmica.'
        self.assertFalse(validate_answer(bad,[dict(n=1,text=inventory)],'Una persona sangra mucho.','es')[0])

    def test_cpr_paraphrases_preserve_conjunction(self):
        for breathing in ('gasping','breathing abnormally'):
            good = f'If unresponsive and {breathing}, start CPR [S1].'
            src = [dict(n=1,text=good)]
            self.assertTrue(validate_answer(good,src,'Someone collapsed.')[0])
            self.assertFalse(validate_answer(good.replace(' and ', ' or '),src,'Someone collapsed.')[0])
            self.assertFalse(validate_answer('If unresponsive and breathing normally, start CPR [S1].',src,'Someone collapsed.')[0])

if __name__ == '__main__':
    unittest.main()
