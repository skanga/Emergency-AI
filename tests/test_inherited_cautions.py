"""Do not turn parent procedure steps into child-section cautions."""
import unittest
from app.passages import extract_passages


class InheritedCautionTests(unittest.TestCase):
    def child(self, parent, child='Start infant CPR with two thumbs or the heel of one hand.'):
        html = '<h1>Infants</h1>' + parent + '<h2 id="unconscious">Unconscious infants</h2><p>' + child + '</p>'
        return next(p for p in extract_passages(html) if p.anchor == 'unconscious')

    def test_parent_chest_thrusts_do_not_become_unconscious_cpr(self):
        parent = '<p>In the chest thrusts manoeuver, press with only two fingers. Abdominal thrusts are not recommended in children less than one year old because they can cause liver damage.</p>'
        p = self.child(parent)
        self.assertNotIn('only two fingers', p.text)
        self.assertIn('two thumbs', p.text)
        self.assertIn('Abdominal thrusts are not recommended', p.text)

    def test_standalone_scope_cautions_survive(self):
        for text in ('Only for infants.', 'This procedure is for adults only.', 'Somente para adultos.', 'Do not perform blind finger sweeps.',
                     'If the object is not visible, do not attempt to extract it.',
                     'Nunca faça varredura às cegas.', 'No introduzca los dedos a ciegas.'):
            with self.subTest(text=text):
                self.assertIn(text, self.child('<p>' + text + '</p>').text)

    def test_mixed_list_keeps_warning_without_parent_steps(self):
        p = self.child('<ol><li>Give five back blows using only one hand.</li><li>Never perform blind finger sweeps.</li></ol>')
        self.assertNotIn('five back blows', p.text)
        self.assertIn('Never perform blind finger sweeps.', p.text)

    def test_parent_original_and_anchor_are_not_rewritten(self):
        text = 'Press with only two fingers. Do not use abdominal thrusts on an infant.'
        ps = extract_passages('<h1 id="parent">Infants</h1><p>' + text + '</p><h2 id="child">Unconscious infants</h2><p>Start CPR.</p>')
        self.assertEqual(next(p for p in ps if p.anchor=='parent').text, text)
        self.assertNotIn('only two fingers', next(p for p in ps if p.anchor=='child').text)

    def test_only_does_not_make_a_descendant_a_warning_section(self):
        html = '<h1>Guide</h1><h2 id="steps">CPR</h2><p>Start CPR.</p><h3>Using only one hand</h3><p>Unrelated alternative procedure.</p>'
        p = next(p for p in extract_passages(html) if p.anchor=='steps')
        self.assertNotIn('Unrelated alternative', p.text)

    def test_semicolon_does_not_merge_parent_step_with_caution(self):
        p = self.child('<p>Give five chest thrusts using two fingers; never perform blind sweeps.</p>')
        self.assertNotIn('five chest thrusts', p.text)
        self.assertIn('never perform blind sweeps.', p.text)

    def test_nested_list_keeps_treatment_under_its_condition(self):
        html = '<h1>Glucose</h1><ul><li>If awake<ul><li>Oral glucose</li></ul></li><li>If unresponsive<ul><li>Call emergency services</li></ul></li></ul>'
        p = extract_passages(html)[0]
        self.assertIn('- If awake\n  - Oral glucose', p.text)
        self.assertIn('- If unresponsive\n  - Call emergency services', p.text)

    def test_semicolon_condition_stays_with_caution(self):
        text = 'If the person is conscious; do not give rescue breaths.'
        self.assertIn(text, self.child('<p>' + text + '</p>').text)

    def test_nested_warning_retains_its_parent_condition(self):
        p = self.child('<ul><li>If breathing normally<ul><li>Do not start CPR.</li></ul></li></ul>')
        self.assertIn('If breathing normally\nDo not start CPR.', p.text)

    def test_ambiguous_conditional_prose_is_not_transplanted(self):
        for text in ('If breathing normally, monitor closely. Do not start CPR.',
                     'If conscious, give five chest thrusts using two fingers; never perform blind sweeps.'):
            p = self.child('<p>' + text + '</p>')
            self.assertNotIn('Do not start CPR', p.text)
            self.assertNotIn('five chest thrusts', p.text)

    def test_skipped_conditional_parent_does_not_orphan_nested_warning(self):
        p = self.child('<ul><li>If breathing normally, monitor closely<ul><li>Do not start CPR.</li></ul></li></ul>')
        self.assertNotIn('Do not start CPR', p.text)
