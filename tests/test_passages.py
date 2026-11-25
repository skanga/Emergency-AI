import unittest
from app.passages import extract_passages


class PassageTests(unittest.TestCase):
    def test_structure_procedure_and_metadata(self):
        html = '<nav>junk</nav><h1>First aid</h1><p>Only for adults.</p><h2 id="help">Help</h2><ol><li>Give 5 blows<ul><li>Support head</li></ul></li><li>Repeat</li></ol><table><tr><th>Dose</th><th>Wait</th></tr><tr><td>2 drops</td><td>30 minutes</td></tr></table><p>Warning: never use on infants.</p><footer>junk</footer><script>junk</script>'
        result = extract_passages(html, archive='book', version='2026', article_url='/article')
        p = next(p for p in result if p.anchor == 'help')
        self.assertEqual(p.heading_path, ('First aid', 'Help'))
        for term in ('Only for adults.', '1. Give 5 blows', 'Support head', '2. Repeat', 'Dose | Wait', '2 drops | 30 minutes', 'Warning: never use on infants.'):
            self.assertIn(term, p.text)
        self.assertNotIn('junk', p.text)
        self.assertEqual((p.archive, p.version, p.article_url), ('book', '2026', '/article'))
        self.assertEqual(result, extract_passages(html, archive='book', version='2026', article_url='/article'))

    def test_late_section_and_complete_blocks(self):
        html = '<h1>Guide</h1>' + '<p>' + 'Long prose. ' * 10000 + '</p><h2>Final section</h2><ol>' + '<li>Complete step.</li>' * 100 + '</ol><p>Final warning: do not stop.</p>'
        passages = extract_passages(html, max_prose_chars=100)
        final = next(p for p in passages if 'Final section' in p.heading_path)
        self.assertEqual(final.text.count('Complete step.'), 100)
        self.assertIn('Final warning: do not stop.', final.text)
        self.assertEqual(len({p.id for p in passages}), len(passages))
        self.assertEqual(final.anchor, '')

    def test_malformed_and_boilerplate(self):
        html = '<div class="navbox">junk</div><h2><span id="Dose">Dose</span></h2><ol><li>First<li>Second</ol><p>Never exceed 2 mg'
        p = extract_passages(html)[0]
        self.assertNotIn('junk', p.text)
        self.assertIn('1. First', p.text)
        self.assertIn('2. Second', p.text)
        self.assertIn('Never exceed 2 mg', p.text)
        self.assertEqual(p.anchor, 'Dose')

    def test_prose_splits_on_blocks_with_scope_warning(self):
        html = '<h1>Adults</h1><p>Warning: adults only.</p><h2>Details</h2>' + ''.join('<p>' + str(i) + ' abcdefghij.</p>' for i in range(10)) + '<p>Warning: final caution.</p>'
        parts = [p for p in extract_passages(html, max_prose_chars=40) if 'Details' in p.heading_path]
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertIn('Warning: adults only.', part.text)
            self.assertIn('Warning: final caution.', part.text)

    def test_repeated_source_blocks_are_not_deduplicated(self):
        p = extract_passages('<h1>Procedure</h1><p>Repeat check.</p><ol><li>Act</li></ol><p>Repeat check.</p>')[0]
        self.assertEqual(p.text.count('Repeat check.'), 2)

    def test_warning_subsection_stays_with_procedure(self):
        html = '<h1>Guide</h1><h2>Steps</h2><ol><li>First</li><li>Last</li></ol><h3>Warnings</h3><p>Never give food.</p><h2>Another topic</h2><p>Unrelated.</p>'
        p = next(p for p in extract_passages(html) if p.heading_path == ('Guide', 'Steps'))
        self.assertIn('Never give food.', p.text)
        self.assertNotIn('Unrelated.', p.text)

    def test_parent_background_does_not_swamp_specific_procedure(self):
        html = '<h1>Guide</h1><p>' + 'Background. ' * 4000 + '</p><p>Only for adults.</p><h2>First aid</h2><ol><li>First</li><li>Last</li></ol>'
        p = next(p for p in extract_passages(html) if p.heading_path[-1] == 'First aid')
        self.assertNotIn('Background.', p.text)
        self.assertIn('Only for adults.', p.text)

    def test_optional_paragraph_close_before_heading(self):
        html = '<h1>Guide</h1><p>Intro<h2 id="procedure">Procedure</h2><ol><li>First</li><li>Last</li></ol><p>Warning: avoid this'
        p = next(p for p in extract_passages(html) if p.anchor == 'procedure')
        self.assertEqual(p.heading_path, ('Guide', 'Procedure'))
        self.assertIn('1. First', p.text)
        self.assertIn('Warning: avoid this', p.text)

    def test_ordered_list_item_value_preserves_source_number(self):
        p = extract_passages('<h1>Steps</h1><ol start="2"><li>Second</li><li value="4">Fourth</li><li>Fifth</li></ol>')[0]
        self.assertIn('2. Second', p.text)
        self.assertIn('4. Fourth', p.text)
        self.assertIn('5. Fifth', p.text)
