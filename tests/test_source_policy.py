import unittest
from unittest.mock import patch

from app.source_policy import evaluate_conflicts, source_version


class SourcePolicyTests(unittest.TestCase):
    def test_unrelated_numeric_statements_do_not_rescan_every_pair(self):
        from app.query_planner import normalize
        sources = [{'id':str(i),'text':('Background sentence. ' * 100) + f' Add 2 ml of solution number {i}.'} for i in range(40)]
        with patch('app.source_policy.normalize', wraps=normalize) as normalization:
            self.assertEqual(evaluate_conflicts(sources,['synthetic'],{}), [])
        self.assertLessEqual(normalization.call_count, 2 * len(sources))

    def sources(self):
        return [{'id':'local','kind':'kit','text':'Add 2 ml of solution.','source_version':'v1'},
                {'id':'library','kind':'kiwix','text':'Add 4 ml of solution.','source_version':'v2'}]

    def test_scores_dates_and_duplicate_votes_cannot_resolve_disagreement(self):
        sources = self.sources()
        sources[1].update(issued='2026-11-25',retrieval_score=1000)
        conflicts = evaluate_conflicts(sources + [dict(sources[1], id='copy')], ['synthetic'], {})
        self.assertTrue(conflicts)
        self.assertTrue(all(c['resolution'] == 'unresolved' for c in conflicts))
        self.assertEqual(conflicts[0]['versions'], {'local':'v1','library':'v2'})

    def test_reviewed_precedence_requires_exact_versions_and_scope(self):
        rule = {'id':'review-1','topic':'synthetic','scope':{'age_group':'adult'},
                'sources':{'local':'v1','library':'v2'},'preferred_source':'library',
                'reviewer':'Test reviewer','reviewed_at':'2026-11-25','rationale':'Synthetic revised procedure.'}
        policy = {'rules':[rule]}
        conflicts = evaluate_conflicts(self.sources(), ['synthetic'], {'age_group':'adult'}, policy)
        self.assertEqual(conflicts[0]['resolution'], 'reviewed_precedence')
        self.assertEqual(conflicts[0]['preferred_source'], 'library')
        sources = self.sources(); sources[1]['source_version'] = 'v3'
        self.assertTrue(all(c['resolution']=='unresolved' for c in evaluate_conflicts(sources,['synthetic'],{'age_group':'adult'},policy)))
        self.assertTrue(all(c['resolution']=='unresolved' for c in evaluate_conflicts(self.sources(),['synthetic'],{'age_group':'infant'},policy)))

    def test_different_scopes_and_equal_quantities_are_not_conflicts(self):
        sources = self.sources()
        sources[0]['scope'] = {'age_group':'adult'}
        sources[1]['scope'] = {'age_group':'infant'}
        self.assertEqual(evaluate_conflicts(sources,['synthetic'],{}), [])
        sources = self.sources(); sources[1]['text'] = sources[0]['text']
        self.assertEqual(evaluate_conflicts(sources,['synthetic'],{}), [])

    def test_no_unreviewed_precedence_or_filename_authority(self):
        sources = self.sources()
        self.assertNotEqual(source_version({'text':'one','issued':'2026-11-25'}), '2026-11-25')
        policy = {'rules':[{'id':'bad','topic':'synthetic','sources':{'local':'v1','library':'v2'},'preferred_source':'library'}]}
        with self.assertRaises(ValueError):
            evaluate_conflicts(sources,['synthetic'],{},policy)

    def test_known_procedural_conflict_can_be_unresolved(self):
        sources = self.sources(); sources[0]['text']='Use the synthetic method.';sources[1]['text']='Avoid the synthetic method.'
        rule = {'id':'known','topic':'synthetic','sources':{'local':'v1','library':'v2'},
                'reviewer':'Test reviewer','reviewed_at':'2026-11-25','rationale':'Reviewed synthetic disagreement.'}
        conflicts = evaluate_conflicts(sources,['synthetic'],{}, {'rules':[rule]})
        self.assertEqual(conflicts[0]['resolution'],'unresolved')
        self.assertEqual(conflicts[0]['detection_basis'],'reviewed_rule')

    def test_malformed_policy_always_reports_value_error(self):
        base = dict(id='r', topic='synthetic', reviewer='Reviewer', reviewed_at='2026-11-25',
                    rationale='Reason', sources={'local':'v1','library':'v2'})
        for policy in ([], None, {'rules':None}, {'rules':[dict(base, scope=[])]},
                       {'rules':[dict(base, sources={'local':None,'library':'v2'})]},
                       {'rules':[dict(base, reviewed_at='2026-99-99')]}):
            if policy is None:
                continue  # None explicitly requests the shipped policy.
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                evaluate_conflicts(self.sources(), ['synthetic'], {}, policy)

    def test_concentration_or_age_changes_are_not_equivalent_statements(self):
        for left, right in [('For age 2 years add 2 ml.', 'For age 4 years add 4 ml.'),
                            ('Add 2 ml of 5% solution.', 'Add 4 ml of 10% solution.')]:
            sources = self.sources(); sources[0]['text']=left; sources[1]['text']=right
            self.assertEqual(evaluate_conflicts(sources), [])

    def test_incompatible_reviewed_rules_do_not_silently_resolve(self):
        base = dict(topic='synthetic', reviewer='Reviewer', reviewed_at='2026-11-25',
                    rationale='Reason', sources={'local':'v1','library':'v2'})
        policy = {'rules':[dict(base,id='a',preferred_source='local'), dict(base,id='b',preferred_source='library')]}
        records = evaluate_conflicts(self.sources(), ['synthetic'], {}, policy)
        self.assertTrue(any(r['resolution']=='unresolved' for r in records))

    def test_repeated_statements_do_not_hide_earlier_disagreement(self):
        sources = self.sources()
        sources[0]['text'] = 'Add 2 ml of solution.\nAdd 4 ml of solution.'
        self.assertTrue(evaluate_conflicts(sources))

    def test_conditions_in_headings_or_preceding_lines_prevent_false_conflict(self):
        sources = self.sources()
        sources[0]['section'] = 'Infant procedure'
        sources[1]['section'] = 'Adult procedure'
        self.assertEqual(evaluate_conflicts(sources), [])
        sources = self.sources()
        sources[0]['text'] = 'For 5% solution:\nAdd 2 ml of solution.'
        sources[1]['text'] = 'For 10% solution:\nAdd 4 ml of solution.'
        self.assertEqual(evaluate_conflicts(sources), [])

    def test_record_identity_is_independent_of_retrieval_rank(self):
        sources = self.sources()
        self.assertEqual(evaluate_conflicts(sources)[0]['id'], evaluate_conflicts(sources[::-1])[0]['id'])

    def test_unknown_or_missing_policy_schema_fails_closed(self):
        for policy in ({}, {'version':2,'rules':[]}, {'version':True,'rules':[]}):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                evaluate_conflicts(self.sources(), policy=policy)

    def test_numeric_age_qualifiers_in_headings_keep_different_conditions_separate(self):
        for field in ('section', 'title', 'doc_title'):
            sources = self.sources()
            sources[0][field] = 'Age 2 years'
            sources[1][field] = 'Age 4 years'
            with self.subTest(field=field):
                self.assertEqual(evaluate_conflicts(sources), [])
        sources = self.sources()
        sources[0]['section'] = 'Age 2 years'
        self.assertEqual(evaluate_conflicts(sources), [])

    def test_concentrations_in_all_heading_fields_keep_conditions_separate(self):
        for field in ('section', 'title', 'doc_title'):
            sources = self.sources()
            sources[0][field] = '5% solution'
            sources[1][field] = '10% solution'
            with self.subTest(field=field):
                self.assertEqual(evaluate_conflicts(sources), [])
        sources = self.sources()
        sources[0]['title'] = '5% solution'
        self.assertEqual(evaluate_conflicts(sources), [])

    def test_equivalent_decimal_quantities_do_not_create_conflict(self):
        for quantity in ('2.0 ml', '2,00 ml', '02 ml'):
            sources = self.sources()
            sources[1]['text'] = 'Add ' + quantity + ' of solution.'
            with self.subTest(quantity=quantity):
                self.assertEqual(evaluate_conflicts(sources), [])

    def test_ancestor_headings_carry_conditions(self):
        for left, right in [('Age 2 years', 'Age 4 years'), ('5% solution', '10% solution')]:
            sources = self.sources()
            sources[0]['heading_path'] = [left, 'Procedure']
            sources[1]['heading_path'] = [right, 'Procedure']
            with self.subTest(condition=left):
                self.assertEqual(evaluate_conflicts(sources), [])
