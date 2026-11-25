"""Bounded per-request retrieval with complete passages and observable failures."""
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from app.engine import Engine
from app.kiwix import KiwixClient


def client_with_books(count=1):
    client = KiwixClient('http://localhost:8092')
    client._books = [dict(name=f'book{i}', served_name=f'book{i}', title=f'Library {i}',
                          lang='eng', archive_uuid=f'uuid{i}', issued='2026-10') for i in range(count)]
    return client


def result(title, path):
    return f'<item><title>{title}</title><link>/content/book0/{path}</link></item>'


class PipelineTests(unittest.TestCase):
    def engine(self, count=1):
        engine = Engine({'kiwix_enabled': True})
        engine.kiwix = client_with_books(count)
        engine.kb.search = Mock(return_value=[])
        return engine

    def test_every_library_before_second_query_and_budget_visible(self):
        engine = self.engine(23)
        diagnostics = {}
        calls = []
        def fetch(url, **kwargs):
            calls.append(parse_qs(urlsplit(url).query)['books.name'][0])
            return '<rss/>'
        with patch('app.kiwix.get_text', side_effect=fetch):
            engine.retrieve('seizure first aid', 'en', diagnostics=diagnostics)
        self.assertEqual(len(calls), 20)
        self.assertEqual(len(set(calls)), 20)
        self.assertEqual(sum(d['status'] == 'not_searched_budget' for d in diagnostics['libraries']), 3)

    def test_rejects_wrong_topic_then_fetches_later_valid_passage(self):
        engine = self.engine()
        def fetch(url, **kwargs):
            if '/search?' in url:
                return '<rss><channel>' + result('Seizure Salad', 'salad') + result('Seizure', 'seizure') + '</channel></rss>'
            if url.endswith('salad'):
                return '<h1>Seizure Salad</h1><p>Recipe for lettuce and dressing.</p>'
            return '<h1>Seizure</h1><h2>History</h2><p>' + 'Historical discussion. ' * 5000 + '</p><h2 id="aid">First aid</h2><ol><li>Protect the person from injury during a seizure.</li><li>Do not restrain.</li></ol>'
        with patch('app.kiwix.get_text', side_effect=fetch):
            sources = engine.retrieve('seizure first aid', 'en')
        self.assertTrue(sources)
        self.assertIn('Protect the person', sources[0]['text'])
        self.assertEqual(sources[0]['anchor'], 'aid')
        self.assertTrue(sources[0]['link'].endswith('#aid'))
        self.assertEqual(sources[0]['archive_uuid'], 'uuid0')

    def test_disabled_and_empty_selection_are_explicit(self):
        for options, status in [({'use_kiwix': False}, 'disabled'), ({'kiwix_books': []}, 'no_selection')]:
            engine = self.engine()
            diagnostics = {}
            with patch('app.kiwix.get_text') as fetch:
                engine.retrieve('burn', 'en', diagnostics=diagnostics, **options)
            fetch.assert_not_called()
            self.assertEqual(diagnostics['status'], status)
            engine.kb.search.assert_called()

    def test_slow_worker_does_not_hold_request_past_deadline(self):
        engine = self.engine(12)
        diagnostics = {}
        def slow(*args, **kwargs):
            time.sleep(.25)
            return '<rss/>'
        with patch('app.retrieval.REQUEST_SECONDS', .04), patch('app.kiwix.get_text', side_effect=slow):
            start = time.monotonic()
            engine.retrieve('burn', 'en', diagnostics=diagnostics)
            self.assertLess(time.monotonic() - start, .18)
        self.assertTrue(any(d['status'] == 'timeout' for d in diagnostics['libraries']))
        time.sleep(.26)

    def test_retrieval_event_and_done_are_request_owned(self):
        engine = self.engine()
        with patch('app.kiwix.get_text', return_value='<rss/>'):
            events = list(engine.answer('burn', use_llm=False))
        kinds = [kind for kind, _ in events]
        self.assertLess(kinds.index('retrieval'), kinds.index('token'))
        report = next(value for kind, value in events if kind == 'retrieval')
        self.assertEqual(events[-1][1]['retrieval'], report)
        self.assertEqual(report['included'], 0)

class TransportAndCacheTests(unittest.TestCase):
    def test_missing_content_length_is_still_bounded(self):
        import io
        from email.message import Message
        from app.net import get_bytes, ResponseTooLarge
        response = Mock(spec=["headers", "read", "__enter__", "__exit__"])
        response.headers = Message()
        response.read = io.BytesIO(b'123456789').read
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('app.net.open_url', return_value=response):
            with self.assertRaises(ResponseTooLarge):
                get_bytes('http://localhost/', max_bytes=8)

    def test_passage_cache_keys_include_archive_version(self):
        client = client_with_books()
        hit = dict(book_name='book0', link='/content/book0/Burn', archive_uuid='first', issued='2026-01')
        with patch('app.kiwix.get_text', return_value='<h1>Burn</h1><p>Cool the burn.</p>') as fetch:
            first = client.article_passages(hit)
            self.assertEqual(client.article_passages(hit), first)
            self.assertEqual(fetch.call_count, 1)
            second = client.article_passages(dict(hit, archive_uuid='second'))
            self.assertEqual(fetch.call_count, 2)
            self.assertNotEqual(first[0].id, second[0].id)
            self.assertEqual(len(client._cache), 1)

    def test_foreign_redirect_is_rejected(self):
        from app import net
        self.assertTrue(hasattr(net, 'SameOriginRedirectHandler'))
        import urllib.request
        handler = net.SameOriginRedirectHandler('http://localhost:8092')
        with self.assertRaises(ValueError):
            handler.redirect_request(urllib.request.Request('http://localhost:8092/a'), None, 302, 'Found', {}, 'https://foreign.invalid/x')

    def test_scope_and_incidental_titles(self):
        from app.retrieval import relevance
        from app.query_planner import plan_query
        plan = plan_query('my 5 month old baby is choking')
        for heading in ('Adult choking', 'Neonatal resuscitation'):
            self.assertEqual(relevance(dict(title='CPR', section=heading, text='Infant care and choking procedure'), plan), 0)
        self.assertGreater(relevance(dict(title='Choking', section='Infant first aid', text='Protect the baby.'), plan), 0)
        for question, title in [('seizure first aid', 'Seizure Salad'), ('stroke first aid', '2 stroke diesel engine'), ('baby choking', 'Infant Optics'), ('carbon monoxide poisoning', 'CO detector teardown')]:
            self.assertEqual(relevance(dict(title=title), plan_query(question)), 0)
        self.assertGreater(relevance(dict(title='Food processor repair', text='Repair your food processor'), plan_query('repair food processor')), 0)

    def test_one_failed_and_all_failed_searches_are_not_zero_hits(self):
        for failures, expected in [(1, 'partial'), (2, 'failed'), (0, 'zero_hits')]:
            engine = Engine({'kiwix_enabled': True})
            engine.kiwix = client_with_books(2)
            engine.kb.search = Mock(return_value=[])
            def fetch(url, **kwargs):
                name = parse_qs(urlsplit(url).query)['books.name'][0]
                if int(name[-1]) < failures:
                    raise TimeoutError('slow')
                return '<rss/>'
            report = {}
            with patch('app.kiwix.get_text', side_effect=fetch):
                engine.retrieve('seizure', 'en', diagnostics=report)
            self.assertEqual(report['status'], expected)

class PreparedIndexTests(unittest.TestCase):
    def test_prepared_selected_document_participates_in_retrieval(self):
        import tempfile
        from app.document_index import DocumentIndex
        engine = Engine({'kiwix_enabled': True})
        engine.kiwix = client_with_books()
        engine.kb.search = Mock(return_value=[])
        with tempfile.TemporaryDirectory() as root:
            engine.settings['document_index_dir'] = root
            DocumentIndex(root).replace(engine.kiwix._books[0], [dict(text='Seizure first aid. Protect the person from injury.', title='Emergency care', page=2, link='/content/book0/guide.pdf#page=2', document_hash='abc')], {})
            report = {}
            with patch('app.kiwix.get_text', return_value='<rss/>'):
                sources = engine.retrieve('seizure first aid', 'en', diagnostics=report)
            self.assertEqual(sources[0]['page'], 2)
            self.assertEqual(report['libraries'][0]['index']['state'], 'indexed')

class BudgetFailureTests(unittest.TestCase):
    def test_fetch_oversize_is_not_zero_hits(self):
        from app.net import ResponseTooLarge
        engine = Engine({'kiwix_enabled': True})
        engine.kiwix = client_with_books()
        engine.kb.search = Mock(return_value=[])
        def fetch(url, **kwargs):
            if '/search?' in url:
                return '<rss>' + result('Burn first aid', 'Burn') + '</rss>'
            raise ResponseTooLarge('too big')
        report = {}
        with patch('app.kiwix.get_text', side_effect=fetch):
            self.assertEqual(engine.retrieve('burn first aid', 'en', diagnostics=report), [])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['fetches'][0]['status'], 'oversize')

    def test_search_and_fetch_concurrency_and_caps(self):
        import threading
        engine = Engine({'kiwix_enabled': True})
        engine.kiwix = client_with_books(12)
        engine.kb.search = Mock(return_value=[])
        active, peak = 0, 0
        lock = threading.Lock()
        def fetch(url, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(.001)
                if '/search?' in url:
                    book = parse_qs(urlsplit(url).query)['books.name'][0]
                    return '<rss>' + ''.join(result('Burn first aid', book + str(i)) for i in range(8)) + '</rss>'
                return '<h1>Burn</h1><h2>First aid</h2><p>Cool the burn with running water.</p>'
            finally:
                with lock:
                    active -= 1
        report = {}
        with patch('app.kiwix.get_text', side_effect=fetch):
            sources = engine.retrieve('burn first aid', 'en', diagnostics=report)
        self.assertTrue(sources)
        self.assertLessEqual(peak, 4)
        self.assertEqual(report['searches'], 20)
        self.assertEqual(report['fetched'], 12)
        self.assertEqual(report['candidates'], 40)
        self.assertTrue(all(r['attempts'] for r in report['libraries']))

    def test_catalog_error_is_returned_to_its_caller(self):
        client = KiwixClient('http://localhost:8092')
        report = []
        with patch('app.kiwix.get_text', return_value='<html>bad</html>'):
            self.assertEqual(client.books(diagnostics=report), [])
        self.assertEqual(report[0]['failure_status'], 'parse_error')

class CandidateSelectionRegressions(unittest.TestCase):
    def test_second_query_valid_hit_survives_full_first_query_and_avoids_collision_fetches(self):
        from app.query_planner import plan_query
        engine = Engine({'kiwix_enabled': True})
        engine.kiwix = client_with_books()
        engine.kb.search = Mock(return_value=[])
        first = plan_query('seizure first aid').queries_by_language['en'][0]
        fetched = []
        def fetch(url, **kwargs):
            if '/search?' in url:
                query = parse_qs(urlsplit(url).query)['pattern'][0]
                if query == first:
                    return '<rss>' + ''.join(result('Seizure Salad', 'salad' + str(i)) for i in range(8)) + '</rss>'
                return '<rss>' + result('Seizure first aid', 'aid') + '</rss>'
            fetched.append(url)
            return '<h1>Seizure</h1><h2>First aid</h2><p>Protect the person during the seizure.</p>'
        with patch('app.kiwix.get_text', side_effect=fetch):
            sources = engine.retrieve('seizure first aid', 'en')
        self.assertTrue(sources)
        self.assertEqual([s['link'] for s in sources], ['/content/book0/aid'])
        self.assertEqual(fetched, ['http://localhost:8092/content/book0/aid'])

    def test_weak_library_does_not_displace_stronger_local_context(self):
        from app.retrieval import select_sources
        local = [dict(id='local-best', retrieval_score=100), dict(id='local-next', retrieval_score=99)]
        library = [dict(id='weak-library', retrieval_score=.1)]
        self.assertEqual([s['id'] for s in select_sources(local, library, 5, 3)],
                         ['local-best', 'local-next', 'weak-library'])

    def test_joint_selection_protects_local_then_ranks_both_origins(self):
        from app.retrieval import select_sources
        local = [dict(id='local-best', retrieval_score=10), dict(id='local-next', retrieval_score=5)]
        library = [dict(id='library-best', retrieval_score=20), dict(id='library-next', retrieval_score=2)]
        self.assertEqual([s['id'] for s in select_sources(local, library, 5, 3)],
                         ['local-best', 'library-best', 'local-next', 'library-next'])

class EvidenceApplicabilityTests(unittest.TestCase):
    def test_references_and_translation_stubs_are_not_evidence(self):
        from app.query_planner import plan_query
        from app.retrieval import relevance
        for section, body in [
            ('References › Anaphylaxis treatment', 'Smith et al. Anaphylaxis treatment. Journal of medicine. 2020; 10:42.'),
            ('Bibliography', 'Anaphylaxis: treatment review. doi:10.1000/test'),
            ('Cardiopulmonary resuscitation', 'This page is a translated version of CPR. Translation progress: 0%.'),
        ]:
            plan = plan_query('anaphylaxis' if 'Anaphylaxis' in body else 'CPR')
            self.assertEqual(relevance(dict(title=section, section=section, text=body, kind='kiwix'), plan), 0)

    def test_emergency_requires_direct_topic_evidence_but_keeps_personal_procedure(self):
        from app.query_planner import plan_query
        from app.retrieval import local_sources
        from app.knowledge import Chunk
        kb = Mock()
        unrelated = Chunk('bad', 'en', 'first-aid', 'First aid', 'Severe bleeding', 'bleeding', 'Protect the person. Do not give water. Call for help.')
        personal = Chunk('good', 'en', 'extra/my-plan', 'My seizure plan', 'First aid', 'aid', 'Protect my head with a cushion. Time the episode. Call my caregiver.')
        kb.search.return_value = [(100, unrelated), (1, personal)]
        found = local_sources(kb, plan_query('Someone has a seizure, what should I do?'), 'en', 5)
        self.assertEqual([s['id'] for s in found], ['good'])

    def test_choking_does_not_assume_unconsciousness(self):
        from app.query_planner import plan_query
        from app.retrieval import relevance
        source = dict(title='Choking', section='Unconscious infants', text='For choking, begin chest compressions and call for help.', kind='kiwix')
        self.assertEqual(relevance(source, plan_query('My 5 month old is choking and turning blue')), 0)
        self.assertGreater(relevance(source, plan_query('My 5 month old is choking and unconscious')), 0)
        source['section'] = 'Conscious infants'
        self.assertEqual(relevance(source, plan_query('My 5 month old is choking and unresponsive')), 0)

    def test_fit_error_still_emits_diagnostics_before_tokens(self):
        from app.llm import LLMError
        engine = Engine({'kiwix_enabled': False})
        engine.llm = Mock(return_value=Mock())
        engine.fit_messages = Mock(side_effect=LLMError('too large'))
        kinds = [kind for kind, _ in engine.answer('CPR')]
        self.assertLess(kinds.index('retrieval'), kinds.index('token'))
        self.assertLess(kinds.index('sources'), kinds.index('token'))

    def test_unstarted_fetches_are_not_counted_as_attempts(self):
        from app import retrieval
        from app.query_planner import plan_query
        client = client_with_books()
        def search(book, query, deadline=None):
            return [dict(title='Burn first aid', link='/article'+str(i), book='Library', book_name='book0', native_rank=i+1, queries=[query]) for i in range(8)], dict(status='success', hits=8)
        client.search_book = search
        fetched = []
        def fetch(hit, deadline=None):
            fetched.append(hit['link'])
            time.sleep(.1)
            return []
        client.article_passages = fetch
        report = {}
        retrieval.library_sources(client, plan_query('burn'), None, report, time.monotonic()+.03)
        self.assertEqual(report['fetched'], len(fetched))
        self.assertEqual(report['not_fetched_budget'], 4)
        time.sleep(.12)

    def test_incidental_emergency_mentions_do_not_promote_other_local_topics(self):
        from app.knowledge import Chunk
        from app.query_planner import plan_query
        from app.retrieval import local_sources
        kb = Mock()
        kb.search.return_value = [(20, Chunk('heat', 'en', 'first-aid', 'First aid', 'Heatstroke', 'heat', 'Seek help for heatstroke. Danger signs include seizures.')),
                                  (10, Chunk('personal', 'en', 'extra/plan', 'My care plan', 'Emergency steps', 'steps', 'During a seizure, protect my head and call my caregiver.'))]
        self.assertEqual([s['id'] for s in local_sources(kb, plan_query('seizure'), 'en', 5)], ['personal'])

class EducationalPageTests(unittest.TestCase):
    def test_emergency_excludes_quizzes_including_translated_subpages(self):
        from app.query_planner import plan_query
        from app.retrieval import relevance
        for title, link in [('Epinephrine Auto-Injector/Quiz', '/content/book/Injector/Quiz'),
                            ('Epinephrine Auto-Injector', '/content/book/Injector/Quiz/es'),
                            ('Anaphylaxis assessment questions', '/content/book/Questions'),
                            ('Anaphylaxis study questions', '/content/book/Study')]:
            source = dict(title=title, link=link, text='Anaphylaxis: administer epinephrine. Which action should you take?', kind='kiwix')
            self.assertEqual(relevance(source, plan_query('anaphylaxis first aid')), 0)

    def test_explicit_quiz_request_and_clinical_assessment_remain_eligible(self):
        from app.query_planner import plan_query
        from app.retrieval import relevance
        quiz = dict(title='Anaphylaxis Quiz', link='/content/book/Quiz', text='Anaphylaxis: administer epinephrine. Which action should you take?', kind='kiwix')
        self.assertGreater(relevance(quiz, plan_query('Show me an anaphylaxis quiz')), 0)
        assessment = dict(title='Anaphylaxis', section='Initial patient assessment', text='Check breathing and call for help.', kind='kiwix')
        self.assertGreater(relevance(assessment, plan_query('anaphylaxis first aid')), 0)
