"""Behavioral contracts for the offline answer-quality evaluation harness."""
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

from tests.evals.emergency_advice import suite


class AdviceEvaluationTests(unittest.TestCase):
    def capture(self, answer='Call for help [1].', **done):
        return {'id': 'example', 'request': {'q': 'Help', 'history': []}, 'answer': answer,
                'events': [{'event': 'sources', 'data': [{'n': 1, 'id': 'a', 'text': 'Call for help.'}]},
                           {'event': 'done', 'data': done}]}

    def test_sse_multiline_and_unicode(self):
        wire = ': heartbeat\n\nevent: token\ndata: "água"\n\nevent: done\ndata: {"mode":\ndata: "llm"}\n\n'
        self.assertEqual(list(suite.sse(io.BytesIO(wire.encode()))),
                         [('token', 'água'), ('done', {'mode': 'llm'})])

    def test_missing_done_is_failure_even_with_plausible_answer(self):
        raw = self.capture(); raw['events'].pop()
        self.assertEqual(suite.normalize(raw)['outcome'], 'incomplete')

    def test_declared_incomplete_and_error_are_not_success(self):
        for done in ({'generation': {'incomplete': True}},):
            self.assertEqual(suite.normalize(self.capture(**done))['outcome'], 'incomplete')
        raw = self.capture(); raw['error'] = 'timeout'
        self.assertEqual(suite.normalize(raw)['outcome'], 'error')

    def test_grouped_and_omitted_citation_identity(self):
        raw = self.capture('Do this [1, 2] and that [3].')
        raw['events'][0]['data'].append({'n': 2, 'id': 'b', 'context_omitted': True})
        result = suite.normalize(raw)
        self.assertEqual(result['checks']['invalid_citation_ids'], [2, 3])
        self.assertEqual(result['checks']['semantic_support'], 'unreviewed')

    def test_withholding_is_not_a_safety_pass(self):
        result = suite.normalize(self.capture('Answer withheld.', reason='answer_validation_failed'))
        self.assertEqual(result['outcome'], 'withheld')
        self.assertEqual(suite.summarize([result], {})['gate'], 'incomplete')

    def test_zero_reviews_and_zero_cases_cannot_pass(self):
        self.assertEqual(suite.summarize([], {})['gate'], 'incomplete')
        self.assertEqual(suite.summarize([suite.normalize(self.capture())], {})['reviewed'], 0)

    def test_reviews_are_bound_to_answer_sources_and_rubric(self):
        result = suite.normalize(self.capture())
        case = {'id': 'example', 'rubric': {'required': ['help']}}
        review = suite.review_template(result, case)
        review['assessments']['usefulness']['rating'] = 4
        with self.assertRaises(ValueError):
            suite.validate_review(review, dict(result, answer='changed'), case)
        with self.assertRaises(ValueError):
            suite.validate_review(review, result, dict(case, rubric={'required': ['other']}))

    def test_compare_rejects_changed_request_pairing(self):
        before = suite.normalize(self.capture()); after = dict(before, request={'q': 'Different'})
        comparison = suite.compare([before], [after], {}, {})
        self.assertEqual(comparison['matched'], 0)
        self.assertEqual(comparison['request_mismatches'], ['example#1'])

    def test_unknown_citation_and_critical_unsafe_cannot_be_averaged_away(self):
        result = suite.normalize(self.capture('Do this [99].'))
        review = {'assessments': {
            'usefulness': {'rating': 4}, 'unsafe': {'rating': 'critical'},
            'citations': {'rating': 'none'}, 'withholding': {'rating': 'none'}}}
        summary = suite.summarize([result], {'example#1': review})
        self.assertEqual(summary['gate'], 'fail')

    def test_eval_directory_is_excluded_from_zip_and_tar(self):
        root = Path(__file__).resolve().parents[1]
        # Disposable repository tests the working attributes and new (uncommitted) suite.
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p / '.gitattributes').write_bytes((root / '.gitattributes').read_bytes())
            fixture = p / 'tests/evals/emergency_advice/cases.json'
            fixture.parent.mkdir(parents=True); fixture.write_text('[]')
            (p / 'emergency.py').write_text('pass')
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            subprocess.run(['git', '-C', tmp, 'add', '.'], check=True)
            tree = subprocess.check_output(['git', '-C', tmp, 'write-tree'], text=True).strip()
            for kind in ('tar', 'zip'):
                data = subprocess.check_output(['git', '-C', tmp, 'archive', '--format='+kind, tree])
                if kind == 'tar':
                    with tarfile.open(fileobj=io.BytesIO(data)) as archive: names = archive.getnames()
                else:
                    with zipfile.ZipFile(io.BytesIO(data)) as archive: names = archive.namelist()
                self.assertIn('emergency.py', names)
                self.assertFalse(any(n.startswith('tests') for n in names))

class RunnerTests(unittest.TestCase):
    def test_live_followup_uses_current_answer_and_keeps_frozen_case(self):
        from tests.evals.emergency_advice.runner import payload_for
        case = {'followup_of': 'parent', 'request': {'q': 'Now?', 'history': []}}
        previous = {'parent': {'request': {'q': 'First?', 'history': []}, 'answer': 'Current answer'}}
        payload = payload_for(case, previous)
        self.assertEqual(payload['history'][-1]['content'], 'Current answer')
        self.assertEqual(case['request']['history'], [])

    def test_stream_exception_retains_received_answer(self):
        from unittest.mock import patch
        from tests.evals.emergency_advice import runner
        stream = io.BytesIO(b'event: token\ndata: "Partial"\n\nevent: token\ndata: broken\n\n')
        with patch.object(runner, 'build_opener') as opener:
            opener.return_value.open.return_value = stream
            raw = runner.ask('http://localhost', {'q': 'test'}, 'partial')
        self.assertEqual(raw['answer'], 'Partial')
        self.assertEqual(suite.normalize(raw)['outcome'], 'error')

    def test_model_unavailable_and_generation_failure_are_not_answers(self):
        for reason in ('model_unavailable', 'ai_disabled'):
            raw = AdviceEvaluationTests().capture('Search notice', reason=reason)
            self.assertEqual(suite.normalize(raw)['outcome'], 'unavailable')
        raw = AdviceEvaluationTests().capture('Search notice', reason='generation_failed')
        self.assertEqual(suite.normalize(raw)['outcome'], 'error')

    def test_omitted_generation_source_is_invalid_even_when_listed(self):
        raw = AdviceEvaluationTests().capture(generation={'included_source_ids': []})
        self.assertEqual(suite.normalize(raw)['checks']['invalid_citation_ids'], [1])

    def test_truncated_sse_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            list(suite.sse(io.BytesIO(b'event: done\ndata: {}')))

    def test_review_requires_evidence_and_rejects_fabricated_quotes(self):
        result = suite.normalize(AdviceEvaluationTests().capture())
        case = {'id': 'example', 'rubric': {'references': ['cpr']}}
        review = suite.review_template(result, case)
        review['assessments']['unsafe'] = {'rating': 'none', 'reason': 'Looks fine', 'evidence': []}
        with self.assertRaisesRegex(ValueError, 'evidence'):
            suite.validate_review(review, result, case)
        review['assessments']['unsafe']['evidence'] = [{'quote': 'Invented quote'}]
        with self.assertRaisesRegex(ValueError, 'absent'):
            suite.validate_review(review, result, case)

    def test_complete_reviews_require_identity(self):
        result = suite.normalize(AdviceEvaluationTests().capture())
        case = {'id': 'example', 'rubric': {'references': []}}
        review = suite.review_template(result, case)
        for d in suite.RATINGS:
            review['assessments'][d] = {'rating': 4 if d == 'usefulness' else 'none',
                                       'reason': 'Test', 'evidence': [{'quote': 'Call for help'}]}
        with self.assertRaisesRegex(ValueError, 'reviewer'):
            suite.validate_review(review, result, case)
        review.update(reviewer='Test reviewer', method='Fixture', reviewed_at='2026-11-25')
        self.assertTrue(suite.validate_review(review, result, case))
        self.assertEqual(suite.summarize([result], {suite.key(result): review})['gate'], 'pass')

    def test_reference_catalog_change_invalidates_review_document(self):
        from tests.evals.emergency_advice import runner
        result = suite.normalize(AdviceEvaluationTests().capture())
        manifest = {'cases': [{'id': 'example', 'rubric': {'references': []}}],
                    'references': {'r': {'url': 'https://example.org/old'}}}
        document = {'review_manifest_sha256': suite.digest(manifest), 'reviews': []}
        manifest['references']['r']['url'] = 'https://example.org/new'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'reviews.json'; runner.write(path, document)
            with self.assertRaisesRegex(ValueError, 'manifest'):
                runner.reviewed(path, [result], manifest)

    def test_committed_reviews_validate_and_comparison_pairs_exact_requests(self):
        from tests.evals.emergency_advice import runner
        manifest = runner.cases_from(runner.HERE / 'cases.json')
        runs, reviews = {}, {}
        for name in ('release-replay', 'current'):
            runs[name] = runner.read(runner.HERE / 'baselines' / (name + '.json'))['results']
            reviews[name] = runner.reviewed(runner.HERE / 'baselines' / (name + '-reviews.json'),
                                            runs[name], manifest)
            self.assertEqual(len(reviews[name]), len(runs[name]))
        comparison = suite.compare(runs['release-replay'], runs['current'],
                                   reviews['release-replay'], reviews['current'])
        self.assertEqual(comparison['matched'], 22)
        self.assertEqual(comparison['request_mismatches'], [])
        self.assertEqual(comparison['paired_after_summary']['total'], 22)

    def test_no_overwrite_of_imported_or_live_evidence(self):
        from tests.evals.emergency_advice.runner import write
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'result.json'; write(p, {'answer': 'first'})
            with self.assertRaises(FileExistsError): write(p, {'answer': 'second'})
            self.assertEqual(json.loads(p.read_text())['answer'], 'first')

    def test_all_historical_requests_and_baseline_answers_are_present(self):
        from tests.evals.emergency_advice.runner import cases_from, read, HERE
        manifest = cases_from(HERE / 'cases.json')
        cases = {c['id']: c for c in manifest['cases'] if c['group'] == 'historical'}
        self.assertEqual(len(cases), 22)
        for name in ('original', 'release-replay'):
            results = read(HERE / 'baselines' / (name + '.json'))['results']
            self.assertEqual({r['id'] for r in results}, set(cases))
            for r in results:
                self.assertEqual(r['request'], cases[r['id']]['request'])
                self.assertTrue(r['raw_sha256'])
                self.assertTrue(r['answer'])

class RunIntegrationTests(unittest.TestCase):
    def test_repeats_have_independent_live_histories_and_durable_files(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from tests.evals.emergency_advice import runner
        manifest = {'cases': [
            {'id': 'parent', 'group': 'live', 'request': {'q': 'first', 'history': []}},
            {'id': 'follow', 'group': 'live', 'followup_of': 'parent',
             'request': {'q': 'next', 'history': []}}]}
        captured = []
        def ask(url, payload, ident, timeout):
            captured.append(payload)
            return {'id': ident, 'request': payload, 'answer': 'answer ' + str(len(captured)),
                    'events': [{'event': 'done', 'data': {}}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'ask', side_effect=ask), \
                patch.object(runner, 'build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{}')
            out = Path(tmp) / 'run'
            args = SimpleNamespace(url='http://localhost', output=out, root=None,
                                   group='all', trials=2, timeout=10)
            self.assertEqual(runner.run(args, manifest), 0)
            self.assertEqual(captured[1]['history'][-1]['content'], 'answer 1')
            self.assertEqual(captured[3]['history'][-1]['content'], 'answer 3')
            self.assertEqual(captured[2]['history'], [])
            self.assertEqual(len(runner.read(out / 'run.json')['results']), 4)
            self.assertTrue((out / 'raw/follow-2.json').exists())

    def test_uncertain_reviews_prevent_pass_and_partial_reviews_are_not_counted(self):
        result = suite.normalize(AdviceEvaluationTests().capture())
        case = {'id': 'example', 'rubric': {'references': []}}
        review = suite.review_template(result, case)
        self.assertEqual(suite.load_reviews({'reviews': [review]}, [result], [case]), {})
        review.update(reviewer='Fixture', method='Test', reviewed_at='2026-11-25')
        for d in suite.RATINGS:
            review['assessments'][d] = {'rating': 4 if d == 'usefulness' else 'none',
                'reason': 'Test', 'evidence': [{'quote': 'Call for help'}]}
        review['assessments']['withholding']['rating'] = 'uncertain'
        loaded = suite.load_reviews({'reviews': [review]}, [result], [case])
        self.assertEqual(suite.summarize([result], loaded)['gate'], 'incomplete')

    def test_safe_alternative_can_make_justified_refusal_useful(self):
        result = suite.normalize(AdviceEvaluationTests().capture('Use safe bottled water.'))
        review = {'assessments': {d: {'rating': 4 if d == 'usefulness' else
                   'justified' if d == 'withholding' else 'none'} for d in suite.RATINGS}}
        self.assertEqual(suite.summarize([result], {suite.key(result): review})['gate'], 'pass')


if __name__ == '__main__':
    unittest.main()
