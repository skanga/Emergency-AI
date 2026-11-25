"""Applicability checks independent of citation count or native search rank."""
import unittest
from app.query_planner import plan_query
from app.retrieval import relevance


def source(title, section, text, kind='kiwix'):
    return dict(title=title, doc_title=title, section=section, text=text, kind=kind)


class RelevanceQualityTests(unittest.TestCase):
    def test_nonmedical_requests_require_the_requested_subject(self):
        for question, title, section, body in [
            ('Repair my Infant Optics baby camera', 'First aid', 'Emergency childbirth', 'Keep the baby warm and check breathing.'),
            ('How do I water a snake plant?', 'Snakebite', 'First aid', 'For a snake bite, call for help and keep still.'),
            ('How does a flood-fill algorithm work?', 'Flood safety', 'First aid', 'Avoid floodwater and call for help.'),
            ('Someone feels strange. What happened?', 'Heatstroke', 'Treatment', 'Cool the person with water and call for help.'),
        ]:
            with self.subTest(question=question):
                self.assertEqual(relevance(source(title, section, body), plan_query(question)), 0)
        self.assertGreater(relevance(source('Snake plant', 'Watering', 'Water the snake plant only when its soil is dry.'), plan_query('How do I water a snake plant?')), 0)

    def test_specialist_or_administrative_sections_are_not_first_aid(self):
        for question, title, section, body in [
            ('Sudden drooping face and slurred speech', 'Stroke', 'Management › Craniectomy', 'For stroke, perform surgery to remove part of the skull.'),
            ('Boiling water spilled on my arm and it is blistering', 'Burn', 'Management › Intravenous fluids', 'For burn treatment give intravenous fluids.'),
            ('Cooking oil is on fire in my pan', 'Fire Services Department', 'Licensing and certification', 'The department gives fire safety certificates.'),
            ('Water flooded the road', 'Flood management', 'Related studies', 'Use reservoirs for flood management.'),
        ]:
            with self.subTest(section=section):
                self.assertEqual(relevance(source(title, section, body), plan_query(question)), 0)

    def test_first_aid_section_outranks_incidental_background(self):
        plan = plan_query('My sister is having a seizure and shaking on the floor')
        first = source('Seizure', 'Management › First aid during a seizure', 'Protect the person and remove dangerous objects. Do not restrain them.')
        background = source('Seizure', 'History', 'Seizure shaking and seizures on the floor have been described for centuries.')
        self.assertGreater(relevance(first, plan), relevance(background, plan))

    def test_local_nonmedical_senses_are_rejected(self):
        for question, title, section, body in [
            ('Sudden drooping face and slurred speech', 'Tools, knots and repairs', 'How to sharpen a knife', 'Use long strokes and keep a consistent angle.'),
            ('My child has diarrhea and dehydration', 'Food preparation', 'Drying', 'Dehydration preserves food; use thin slices.'),
        ]:
            with self.subTest(section=section):
                self.assertEqual(relevance(source(title, section, body, 'kit'), plan_query(question)), 0)

    def test_unconscious_patient_does_not_receive_oral_intake_section(self):
        plan = plan_query('My diabetic husband took insulin and is now unconscious')
        oral = source('Diabetic hypoglycemia', 'Treatment › Intake of glucose by mouth', 'Give glucose by mouth if the patient is conscious and able to swallow.')
        self.assertEqual(relevance(oral, plan), 0)

    def test_canonical_article_beats_disease_subtype_for_unspecified_case(self):
        plan = plan_query('My sister is having a seizure')
        generic = source('Seizure', '', 'Seizures can cause jerking movements.')
        specific = source('Febrile seizure', '', 'A febrile seizure is a seizure associated with fever.')
        self.assertGreater(relevance(generic, plan), relevance(specific, plan))

    def test_requested_general_subject_requires_all_focus_terms(self):
        unrelated = source('Solar photovoltaics', 'Innovative algorithm', 'Use this algorithm for solar power tracking.')
        self.assertEqual(relevance(unrelated, plan_query('How does a flood-fill algorithm work?')), 0)

    def test_food_storage_does_not_select_choking_procedure(self):
        unrelated = source('Infant food safety', 'Solid foods › First aid for choking', 'For choking, give back blows and call for help.')
        self.assertEqual(relevance(unrelated, plan_query('The refrigerator lost power. Is the food safe?')), 0)

    def test_emergency_questions_do_not_select_engineering_or_policy_articles(self):
        for title, section, body in [
            ('In-river flood management', 'Flood control', 'Flood control uses engineered reservoirs to manage flooding.'),
            ('Fukushima Water Contamination', 'Water contamination', 'Treatment of water contamination is a policy debate about the nuclear plant.'),
            ('Safe Drinking Water Act', 'Environmental justice', 'The law protects drinking water and water contamination is regulated.'),
        ]:
            with self.subTest(title=title):
                q = 'Can I drive through floodwater?' if 'flood' in title.lower() else 'Gasoline contaminated our water. Can I drink it?'
                self.assertEqual(relevance(source(title, section, body), plan_query(q)), 0)

    def test_unspecified_stroke_does_not_select_a_specialist_subtype(self):
        specific = source('Cerebellar stroke', 'Management', 'Admit the patient for neurosurgical evaluation.')
        self.assertEqual(relevance(specific, plan_query('Suddenly she has a drooping face and slurred speech')), 0)

    def test_clinician_only_management_is_not_lay_first_aid(self):
        clinical = source('Stroke (main)', 'Management', 'Establish intravenous access. Perform thrombolysis after CT and admit to the stroke unit.')
        self.assertEqual(relevance(clinical, plan_query('Suddenly she has a drooping face and slurred speech')), 0)

    def test_duplicate_pdf_editions_do_not_consume_multiple_context_slots(self):
        from app.retrieval import select_sources
        sources = [dict(id='a', text='First complete procedure.', retrieval_score=30),
                   dict(id='b', text='First complete procedure.', retrieval_score=29),
                   dict(id='c', text='Second complete procedure.', retrieval_score=28)]
        self.assertEqual([s['id'] for s in select_sources([], sources, 0, 2)], ['a', 'c'])
        sources[0]['text'] = 'Use 1.0 units.'
        sources[1]['text'] = 'Use 10 units.'
        self.assertEqual([s['id'] for s in select_sources([], sources, 0, 2)], ['a', 'b'])

    def test_pdf_word_collisions_do_not_become_disaster_advice(self):
        page = source('Where there is no Doctor', 'Page 260', 'GANGRENE. Flood the wound with hydrogen peroxide. Inject penicillin and open the wound.')
        page['page'] = 260
        self.assertEqual(relevance(page, plan_query('Can I drive across the road covered in floodwater?')), 0)
        plants = source('Plants as indicators of ground water', 'Page 58', 'Mesquite grows on the flood plain near the river. These plants use ground water.')
        plants['page'] = 58
        self.assertEqual(relevance(plants, plan_query('Can I drive across the road covered in floodwater?')), 0)

    def test_multilingual_sources_survive_concrete_evidence_filters(self):
        cases = [
            ('pt', 'Há uma enchente na rua', 'Inundação', 'Durante uma inundação, evite atravessar a água da enchente. Mantenha distância.'),
            ('es', 'Hay una inundación en la calle', 'Inundación', 'Nunca camine por el agua de inundación. Mantenga distancia.'),
            ('pt', 'Óleo na frigideira pegou fogo', 'Incêndio', 'Se o óleo pegar fogo, não use água. Cubra a frigideira e desligue o fogão.'),
            ('es', 'El aceite de la sartén está en llamas', 'Incendio aceite de cocina', 'Si el aceite está en llamas, no use agua. Cubra la sartén y apague el fuego.'),
            ('pt', 'A geladeira ficou sem energia. Os alimentos estão seguros?', 'Segurança alimentar', 'Não coma alimentos da geladeira que ficaram muito tempo sem energia.'),
            ('es', 'El refrigerador está sin electricidad. Es segura la comida?', 'Seguridad alimentaria', 'No coma comida del refrigerador si estuvo demasiado tiempo sin electricidad.'),
            ('pt', 'Água do poço com gasolina', 'Contaminação química da água', 'Não use água com gasolina. Ferver não remove todos os contaminantes químicos.'),
            ('es', 'Agua del pozo con gasolina', 'Contaminación química del agua', 'No use agua con gasolina. Hervir no elimina todos los contaminantes químicos.'),
            ('pt', 'Um fio elétrico caiu no carro', 'Segurança elétrica', 'Mantenha distância do fio elétrico de alta tensão. Não saia do carro.'),
            ('es', 'Un cable eléctrico cayó en el coche', 'Seguridad eléctrica', 'Mantenga distancia del cable eléctrico de alta tensión. No salga del coche.'),
            ('pt', 'Como usar hipoclorito na água?', 'Desinfecção da água', 'Use hipoclorito de sódio sem perfume na água. Aguarde o tempo indicado.'),
            ('es', 'Cómo usar hipoclorito en agua?', 'Desinfección del agua', 'Use hipoclorito sin perfume para desinfectar el agua. Espere el tiempo indicado.'),
        ]
        for lang, question, title, body in cases:
            with self.subTest(lang=lang,title=title):
                self.assertGreater(relevance(source(title, 'Primeiros socorros' if lang=='pt' else 'Primeros auxilios', body), plan_query(question,lang)), 0)

    def test_food_safety_outage_evidence_is_not_required_for_cooking(self):
        guide = source('Food safety', 'First aid', 'Cook chicken thoroughly and wash your hands before preparing food.')
        self.assertGreater(relevance(guide, plan_query('Food safety when cooking chicken')), 0)

    def test_self_administered_emergency_treatment_is_not_clinician_only(self):
        mixed = source('Anaphylaxis', 'Management › Epinephrine', 'An epinephrine auto-injector is the primary treatment. Intravenous dosing requires specialist monitoring.')
        self.assertGreater(relevance(mixed, plan_query('Anaphylaxis with a prescribed auto-injector')), 0)

    def test_descriptive_pdf_negation_is_not_an_emergency_instruction(self):
        page = source('Plants as indicators of ground water', 'Page 85', 'These trees do not depend on ground water. The roots grow well in soil wetted by flood waters.')
        page['page'] = 85
        self.assertEqual(relevance(page, plan_query('Can I drive through floodwater?')), 0)

    def test_direct_flood_first_aid_does_not_require_one_fixed_wording(self):
        for body in ('Never enter floodwater. Move to higher ground and call for help.',
                     'Stay out of floodwater. Do not attempt to cross flooded roads.'):
            with self.subTest(body=body):
                self.assertGreater(relevance(source('Flood', 'First aid', body), plan_query('Can I drive through floodwater?')), 0)

    def test_pdf_book_title_is_not_a_procedure_heading(self):
        plan = plan_query('My father is unresponsive and gasping')
        article = source('Cardiac arrest', 'Management › Cardiopulmonary resuscitation', 'Start cardiopulmonary resuscitation and call for help.')
        page = source('First Aid', 'First Aid — page 17', 'Cardiac arrest. Start cardiopulmonary resuscitation and call for help.')
        page['page'] = 17
        # A generic book name must not receive the first-aid-section bonus.
        from app.retrieval import _section_priority
        self.assertEqual(_section_priority(page, plan), 0)
        self.assertGreater(relevance(article, plan), relevance(page, plan))

    def test_local_topic_homonyms_do_not_displace_actual_medical_guides(self):
        cases = [
            ('Sudden drooping face and slurred speech', 'Fire: how to light one', 'Ignition methods', 'Strike the flint with sharp strokes. Keep the tinder dry.'),
            ('Gasoline got into our well water', 'Alcohol: fermentation and uses', '4. Uses', 'Alcohol is a chemical fuel. Do not drink denatured alcohol; dilute with water.'),
            ('My sister is having a seizure', 'First aid', 'Fever', 'Fever can cause a seizure. Keep the person cool.'),
        ]
        for q,title,heading,body in cases:
            with self.subTest(heading=heading):
                self.assertEqual(relevance(source(title,heading,body,'kit'),plan_query(q)),0)

    def test_unstated_special_conditions_do_not_enter_urgent_context(self):
        cases = [
            ('Boiling water spilled on my arm and it is blistering', 'Cement burn', 'Management', 'Wash a cement burn and remove cement.'),
            ('The refrigerator lost power; can we eat the chicken?', 'Infant food safety', 'Commercial baby food', 'Keep infant food refrigerated and discard unsafe food.'),
            ('My friend is bleeding after a cut', 'First aid', 'Emergency childbirth', 'Control bleeding after childbirth and call for help.'),
        ]
        for q,title,heading,body in cases:
            with self.subTest(title=title,heading=heading):
                self.assertEqual(relevance(source(title,heading,body),plan_query(q)),0)

    def test_explicit_plural_age_scope_keeps_matching_sources(self):
        for question, lang, title, body in [
            ('CPR for children', 'en', 'CPR for children', 'Start CPR and call for help.'),
            ('Ressuscitação para crianças', 'pt', 'Ressuscitação cardiopulmonar para crianças', 'Inicie a ressuscitação cardiopulmonar e chame ajuda.'),
            ('Reanimación para niños', 'es', 'Reanimación cardiopulmonar para niños', 'Inicie la reanimación cardiopulmonar y llame ayuda.'),
        ]:
            with self.subTest(lang=lang):
                self.assertGreater(relevance(source('First aid',title,body), plan_query(question,lang)),0)

    def test_medical_usage_heading_is_a_valid_local_procedure(self):
        guide = source('First aid','How to use an epinephrine auto-injector',
                       'For anaphylaxis, use the prescribed epinephrine auto-injector and call for help.','kit')
        self.assertGreater(relevance(guide,plan_query('Anaphylaxis with an auto-injector')),0)
