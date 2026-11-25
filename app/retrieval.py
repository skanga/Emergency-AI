"""Request-owned retrieval budgets, relevance ranking and joint source selection."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import unquote, urlsplit, quote

from .kiwix import failure_status
from .document_index import DocumentIndex, document_state
from .knowledge import STOPWORDS, is_relevant
from .query_planner import normalize, normalize_language

REQUEST_SECONDS = 8
MAX_SEARCHES = 20
MAX_FETCHES = 12
MAX_CANDIDATES = 40


def run_jobs(jobs, function, deadline):
    """At most four active calls, no waiting executor shutdown after deadline.

    Futures never mutate request diagnostics. The caller records all outcomes,
    including work that could not start before the shared deadline.
    """
    jobs = iter(jobs)
    pool = ThreadPoolExecutor(max_workers=4)
    pending = {}
    exhausted = False
    try:
        while pending or not exhausted:
            while len(pending) < 4 and not exhausted and time.monotonic() < deadline:
                try:
                    job = next(jobs)
                except StopIteration:
                    exhausted = True
                else:
                    pending[pool.submit(function, job)] = job
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                for future, job in pending.items():
                    future.cancel()
                    yield job, None, TimeoutError('Request deadline exceeded')
                for job in jobs:
                    yield job, None, TimeoutError('Not started before request deadline')
                return
            if pending:
                done, _ = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
                for future in done:
                    job = pending.pop(future)
                    try:
                        value = future.result()
                    except Exception as exc:
                        yield job, None, exc
                    else:
                        yield job, value, None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _words(text):
    return {word for word in normalize(text).split() if word not in STOPWORDS and len(word) > 1 and not word.isdigit()}


def _title_collision(label, plan):
    # These devices/recipes share emergency vocabulary without that intent.
    equipment = ('salad', 'recipe', 'diesel', 'engine', 'optics', 'camera', 'teardown', 'processor', 'repair')
    return bool(plan.topics) and any(re.search(r'\b' + word + r'\b', label) for word in equipment)


_REFERENCE_HEADING = re.compile(r'\b(references?|bibliograph(?:y|ies)|further reading|external links|referencias|bibliografia|lecturas adicionales|enlaces externos)\b')
_ACTION = re.compile(r'\b(call|check|give|place|keep|protect|remove|avoid|cool|press|hold|support|lay|turn|begin|start|perform|compress(?:ions)?|push|inject|use|administer|seek|move|rinse|wash|cover|wait|time|do not|never|chame|ligue|verifique|coloque|mantenha|proteja|remova|evite|pressione|inicie|aplique|nao|nunca|llame|compruebe|coloque|mantenga|proteja|retire|evite|presione|inicie|aplique|no)\b')


def _topic_evidence(text, plan):
    # Age suffixes scope a query but are not required adjacency in source prose.
    phrases = [normalize(q) for values in plan.queries_by_language.values() for q in values]
    phrases = [re.sub(r' (infant|bebe|lactante)$', '', phrase) for phrase in phrases]
    return any(re.search(r'\b' + re.escape(phrase) + r's?\b', text) for phrase in phrases if phrase)


def _usable_emergency_body(source, plan, label, body):
    if not plan.topics or 'text' not in source:
        return True  # Search hits may have no snippet; fetch before judging evidence.
    if not body:
        return False
    letters = [char for char in source['text'] if char.isalpha()]
    if letters and plan.request_language in ('en', 'pt', 'es'):
        if sum('LATIN' not in unicodedata.name(char, '') for char in letters) > len(letters) / 2:
            return False
    actionable = bool(_ACTION.search(body))
    if any(marker in body for marker in ('translated version', 'translation progress', 'translate this page')) and not actionable:
        return False
    return _topic_evidence(body, plan) or (_topic_evidence(label, plan) and actionable)


_EDUCATIONAL_PAGE = re.compile(r'\b(quiz(?:zes)?|assessment questions|study questions|practice questions|exam questions|self assessment|knowledge check|test your knowledge|questionario|cuestionario|perguntas de estudo|preguntas de estudio)\b')


def _educational_page(source, plan):
    if not plan.topics or _EDUCATIONAL_PAGE.search(normalize(plan.question)):
        return False
    path = unquote(urlsplit(source.get('link', '')).path)
    label = normalize(source.get('title', source.get('doc_title', '')) + ' ' + source.get('section', '') + ' ' + path)
    return bool(_EDUCATIONAL_PAGE.search(label))


def relevance(source, plan):
    """Relevance/applicability only: this score never resolves factual conflict."""
    if _educational_page(source, plan):
        return 0
    title = source.get('title', source.get('doc_title', ''))
    heading = source.get('section', '')
    text = source.get('text', source.get('snippet', ''))
    label = normalize(title + ' ' + heading)
    body = normalize(text)
    if _REFERENCE_HEADING.search(normalize(heading)):
        return 0
    if not _usable_emergency_body(source, plan, label, body):
        return 0
    heading_state = normalize(heading)
    unconscious = bool(re.search(r'\b(unconscious|unresponsive|inconsciente|inconscientes)\b', heading_state))
    conscious = bool(re.search(r'\b(conscious|responsive|consciente|conscientes)\b', heading_state))
    state = plan.scope.get('consciousness')
    if unconscious and not conscious and (state == 'responsive' or (state is None and 'choking' in plan.topics and 'cpr' not in plan.topics)):
        return 0
    if conscious and not unconscious and state == 'unresponsive':
        return 0
    if _title_collision(label, plan):
        return 0
    age = plan.scope.get('age_group')
    groups = {
        'neonatal': ('neonatal', 'neonate', 'newborn', 'recem nascido', 'recien nacido'),
        'infant': ('infant', 'infants', 'baby', 'babies', 'bebe', 'bebes', 'lactente', 'lactante'),
        'child': ('child', 'children', 'crianca', 'criancas', 'nino', 'ninos'),
        'adult': ('adult', 'adults', 'adulto', 'adultos'),
    }
    scoped = {group for group, phrases in groups.items() if any(f' {p} ' in f' {label} ' for p in phrases)}
    if age and scoped and age not in scoped:
        return 0
    if 'neonatal' in scoped and age == 'infant' and 'infant' not in scoped:
        return 0
    queries = [plan.question, ' '.join(plan.context_terms)]
    queries += [q for values in plan.queries_by_language.values() for q in values]
    queries = [q for q in queries if q]
    if not any(is_relevant(q, title + '\n' + heading + '\n' + text) for q in queries):
        return 0
    if not plan.topics and text and not any(is_relevant(q, text) for q in queries):
        return 0
    original = _words(plan.question + ' ' + ' '.join(plan.context_terms))
    terms = set().union(*(_words(q) for q in queries))
    title_hits = len(terms & _words(title))
    heading_hits = len(terms & _words(heading))
    body_hits = len(terms & _words(text))
    score = title_hits * 3 + heading_hits * 5 + min(body_hits, 8) + len(original & _words(text))
    phrases = [normalize(q) for q in queries]
    score += 5 * any(p in label for p in phrases if len(p.split()) > 1)
    procedure = any(p in normalize(heading) for p in ('first aid', 'treatment', 'management', 'what to do', 'procedure', 'primeiros socorros', 'tratamento', 'primeros auxilios', 'tratamiento'))
    if procedure:
        score += 8
    if any(p in normalize(heading) for p in ('history', 'epidemiology', 'background', 'pathophysiology', 'historia')):
        score *= .4
    if any(p in label for p in ('professional', 'clinical protocol', 'advanced life support', 'neonatal resuscitation')):
        score *= .5
    return score or .1


def local_sources(kb, plan, lang, limit):
    """Keep original facts/personal-document terms alongside planned queries."""
    queries = [plan.question]
    if plan.context_terms:
        queries.append(' '.join(plan.context_terms) + ' ' + plan.question)
    queries.extend(plan.queries_by_language.get(normalize_language(lang), ()))
    found = {}
    for query in dict.fromkeys(queries):
        for native_score, chunk in kb.search(query, lang, k=max(12, limit * 3)):
            source = chunk.to_dict(score=native_score)
            if plan.topics:
                direct = _topic_evidence(normalize(source['section'] + ' ' + source['doc_title']), plan)
                personal = source.get('doc_id', '').startswith('extra/')
                if not direct and not (personal and _topic_evidence(normalize(source['text']), plan)):
                    continue
            score = relevance(source, plan)
            if score > 0:
                source['retrieval_score'] = score
                found[source['id']] = source
    return sorted(found.values(), key=lambda s: s['retrieval_score'], reverse=True)


def library_sources(client, plan, selection, diagnostics, deadline, index_root=None):
    """Search every selected edition once before spending any second queries."""
    diagnostics.update(libraries=[], fetches=[], searches=0, fetched=0, candidates=0)
    # Catalog cache has an expiry independent of the status endpoint's probe.
    if client._catalog_checked and time.monotonic() - client._catalog_checked > 15:
        client._books = None
    def catalog(_):
        errors = []
        books = client.books(deadline=deadline, diagnostics=errors)
        return books, errors
    _, outcome, error = next(run_jobs([None], catalog, deadline))
    books, catalog_errors = outcome if outcome is not None else ([], [])
    if error or catalog_errors:
        diagnostics.update(status='catalog_error', catalog_error=str(error) if error else catalog_errors[0]['error'],
                           catalog_failure=failure_status(error) if error else catalog_errors[0]['failure_status'])
        return []
    if selection is not None:
        absent = set(selection) - {b['name'] for b in books}
        diagnostics['libraries'].extend(dict(name=name, status='identity_error', error='Selection absent from catalog', attempts=[]) for name in sorted(absent))
        books = [b for b in books if b['name'] in selection]
    reports, queries = [], []
    for book in books:
        language = normalize_language(book.get('lang', '').split(',')[0])
        planned = plan.queries_by_language.get(language)
        limited = planned is None
        if planned is None:
            planned = (normalize(plan.question),)
        queries.append(planned[:2])
        report = dict(name=book['name'], served_name=book.get('served_name'), archive_uuid=book.get('archive_uuid', ''),
                      issued=book.get('issued', ''), status='not_searched_budget', attempts=[], hits=0,
                      limited_cross_language=limited)
        reports.append(report)
        diagnostics['libraries'].append(report)
    hits_by_book = [[] for _ in books]
    for round_index in range(2):
        slots = MAX_SEARCHES - diagnostics['searches']
        jobs = [(i, queries[i][round_index]) for i in range(len(books)) if len(queries[i]) > round_index][:slots]
        if time.monotonic() >= deadline:
            break
        for (index, query), outcome, error in run_jobs(jobs, lambda job: client.search_book(books[job[0]], job[1], deadline=deadline), deadline):
            report = reports[index]
            if error and str(error).startswith('Not started'):
                continue
            diagnostics['searches'] += 1
            if error:
                outcome = ([], dict(status=failure_status(error), error=str(error), query=query, hits=0))
            hits, attempt = outcome
            report['attempts'].append(attempt)
            report['hits'] += len(hits)
            if hits or report['status'] != 'success':
                report['status'] = attempt['status']
            hits_by_book[index].extend(hits)
    # Rank both query rounds before the per-library cap. Native rank breaks
    # ties across queries, so an earlier query cannot occupy every tied slot.
    diagnostics['candidate_rejections'] = []
    for i, hits in enumerate(hits_by_book):
        unique = {}
        for hit in hits:
            if _title_collision(normalize(hit['title']), plan) or _educational_page(hit, plan):
                diagnostics['candidate_rejections'].append(dict(link=hit['link'], name=hit['book_name'],
                                                                reason='educational_page' if _educational_page(hit, plan) else 'topic_collision'))
                continue
            key = hit['link']
            if key in unique:
                unique[key]['queries'] = list(dict.fromkeys(unique[key]['queries'] + hit['queries']))
                unique[key]['native_rank'] = min(unique[key]['native_rank'], hit['native_rank'])
            else:
                unique[key] = dict(hit)
        hits_by_book[i] = sorted(unique.values(), key=lambda h: (-relevance(h, plan), h['native_rank']))[:8]
    # Interleave native ranks across libraries before bounding the candidate pool.
    candidates = {}
    for rank in range(16):
        for hits in hits_by_book:
            if rank >= len(hits):
                continue
            hit = hits[rank]
            key = (hit.get('archive_uuid') or hit.get('served_name'), hit['link'])
            if key in candidates:
                candidates[key]['queries'] = list(dict.fromkeys(candidates[key]['queries'] + hit['queries']))
            elif len(candidates) < MAX_CANDIDATES:
                candidates[key] = dict(hit)
    diagnostics['candidates'] = len(candidates)
    ordered = sorted(candidates.values(), key=lambda h: relevance(h, plan), reverse=True)
    # Search snippets can be absent; zero lexical score alone is not a reason
    # to skip fetching a native full-text result. Filter on extracted evidence.
    sources = []
    index = DocumentIndex(index_root or Path(__file__).resolve().parent.parent / 'indexes')
    def search_index(i):
        return document_state(books[i], index), index.search(queries[i], [books[i]], limit=12)
    for i, outcome, error in run_jobs(range(len(books)), search_index, deadline):
        if error:
            reports[i]['index'] = dict(state='unavailable', reason=failure_status(error))
            continue
        state, rows = outcome
        reports[i]['index'] = state
        for native_rank, row in enumerate(rows, 1):
            source = dict(row, kind='kiwix', doc_title=books[i]['title'],
                          section=row['title'] + ' — page ' + str(row['page']),
                          archive=books[i]['name'], version=books[i].get('archive_uuid', ''),
                          native_rank=native_rank, queries=list(queries[i]), anchor='page=' + str(row['page']))
            score = relevance(source, plan)
            if score:
                source['retrieval_score'] = score
                sources.append(source)
    diagnostics['not_fetched_budget'] = max(0, len(ordered) - MAX_FETCHES)
    for hit, passages, error in run_jobs(ordered[:MAX_FETCHES], lambda h: client.article_passages(h, deadline=deadline), deadline):
        diagnostic = dict(link=hit['link'], name=hit['book_name'])
        if error and str(error).startswith('Not started'):
            diagnostics['not_fetched_budget'] += 1
            diagnostics['fetches'].append(dict(diagnostic, status='not_fetched_budget'))
            continue
        diagnostics['fetched'] += 1
        if error:
            diagnostic.update(status=failure_status(error), stage='fetch', error=str(error) or type(error).__name__)
        else:
            accepted = 0
            for passage in passages:
                source = dict(kind='kiwix', id=passage.id, doc_title=hit['book'], title=hit['title'],
                              section=' › '.join(passage.heading_path) or hit['title'], heading_path=list(passage.heading_path),
                              anchor=passage.anchor, link=hit['link'].split('#')[0] + ('#' + quote(passage.anchor, safe='') if passage.anchor else ''), article_url=hit['link'], text=passage.text,
                              book_name=hit['book_name'], archive=passage.archive, version=passage.version,
                              archive_uuid=hit.get('archive_uuid', ''), issued=hit.get('issued', ''),
                              native_rank=hit['native_rank'], queries=hit['queries'])
                score = relevance(source, plan)
                if score:
                    source['retrieval_score'] = score
                    sources.append(source)
                    accepted += 1
            diagnostic.update(status='success' if accepted else ('empty_content' if not passages else 'rejected'), passages=accepted)
        diagnostics['fetches'].append(diagnostic)
    attempted = [r for r in reports if r['attempts']]
    succeeded = [r for r in attempted if r['status'] in ('success', 'zero_hits')]
    diagnostics['status'] = ('success' if sources else 'zero_hits') if len(succeeded) == len(reports) and not any(r['status'] == 'identity_error' for r in diagnostics['libraries']) else ('partial' if succeeded else 'failed')
    fetch_failures = [f for f in diagnostics['fetches'] if f['status'] not in ('success', 'rejected', 'empty_content')]
    if fetch_failures:
        diagnostics['status'] = 'partial' if sources or len(fetch_failures) < len(diagnostics['fetches']) else 'failed'
    return sorted(sources, key=lambda s: (-s['retrieval_score'], s.get('native_rank', 0),
                                          s.get('book_name', ''), s.get('link', ''), s.get('id', '')))


def select_sources(local, library, local_limit, library_limit):
    """Protect the best local result, then jointly rank the remaining evidence.

    Per-origin limits are ceilings, not a priority or a required source quota.
    Scores express applicability only; factual conflicts remain for policy.
    """
    local, library = list(local[:max(0, local_limit)]), list(library[:max(0, library_limit)])
    protected = local[:1]
    remaining = sorted(local[1:] + library, key=lambda s: s['retrieval_score'], reverse=True)
    return protected + remaining
