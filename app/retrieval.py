"""Request-owned retrieval budgets, relevance ranking and joint source selection."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import unquote, urlsplit, quote

from .applicability import inapplicability_reason
from .kiwix import failure_status
from .document_index import DocumentIndex, document_state
from .knowledge import STOPWORDS, is_relevant
from .query_planner import matching_topics, normalize, normalize_language, topic_terms, has_topic_evidence

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
    phrases = list(topic_terms(plan.topics)) if plan.topics else [normalize(q) for values in plan.queries_by_language.values() for q in values]
    phrases = [re.sub(r' (infant|bebe|lactante)$', '', phrase) for phrase in phrases]
    return any(re.search(r'\b' + re.escape(phrase) + r's?\b', text) for phrase in phrases if phrase)


# These are applicability filters, not assertions of source authority.
_BACKGROUND = re.compile(r'\b(history|historical|epidemiology|pathophysiology|references|bibliography|regulations|jurisdiction|licensing|certification|organisational|organizational|related studies|related articles|news|comments|suppliers|research|in development|long term|rehabilitation|environmental justice|quality standards|safe drinking water act|climate services|hydro power|hydroelectric|flood control|in river flood management|historia|epidemiologia)\b')
_SPECIALIST = re.compile(r'\b(craniectomy|thrombolysis|endovascular|surgery|intravenous fluids|airway management|intubation|medications|additional medications|stroke unit|blood pressure|second line|2nd line|hyponatremia|advanced treatment|extracorporeal|alternative medicine|ischemic stroke|hemorrhagic stroke|chronic poisoning)\b')
_VAGUE = {'someone', 'somebody', 'something', 'strange', 'odd', 'happened', 'feels', 'feeling', 'explain', 'please', 'help', 'today', 'tell', 'person', 'people', 'now', 'alguem', 'algo', 'pessoa', 'alguien', 'persona'}


def _local_domain_mismatch(source, plan):
    title = normalize(source.get('doc_title', ''))
    heading = normalize(source.get('section', ''))
    medical = set(plan.topics) - {'fire', 'flood', 'food_safety', 'water_disinfection', 'water_chemical', 'electrical', 'carbon_monoxide'}
    if medical and any(word in title for word in ('tools', 'knots', 'ferramentas', 'herramientas', 'food', 'alimentos', 'comida', 'alcohol', 'alcool', 'fire', 'fogo', 'fuego', 'hygiene', 'higiene', 'energy', 'energia', 'gardening', 'horta', 'huerta', 'checklist', 'listas')):
        return True
    if medical and any(word in heading for word in ('stockpile', 'kit', 'priorities', 'devices', 'checklist', 'estoque', 'reservas', 'maintenance', 'mantenimiento', 'manutencao')):
        return True
    if set(plan.topics) & {'water_chemical', 'water_disinfection'} and any(word in title for word in ('alcohol', 'alcool')):
        return True
    return False


def _general_relevance(source, plan):
    label = normalize(source.get('title', source.get('doc_title', '')) + ' ' + source.get('section', ''))
    body = normalize(source.get('text', source.get('snippet', '')))
    focus = plan.scope.get('focus_terms', ())
    if focus:
        return all(' ' + phrase + ' ' in ' ' + label + ' ' for phrase in focus)
    terms = _words(plan.question + ' ' + ' '.join(plan.context_terms)) - _VAGUE
    if not terms:
        return False
    # Preserve existing multilingual synonyms and singular/plural matching.
    # Generic titles are valid when the body establishes multiple query terms.
    matches = sum(is_relevant(term, label + ' ' + body) for term in terms)
    return matches >= min(2, len(terms))


def _section_priority(source, plan):
    title = normalize(source.get('title', source.get('doc_title', '')))
    heading = normalize(source.get('section', ''))
    # PDF page labels repeat the book title, not an extracted procedure heading.
    leaf = '' if source.get('page') else normalize(source.get('section', '').split(' › ')[-1])
    concepts = topic_terms(plan.topics)
    score = 40 if title in concepts else 0
    if any(p in leaf for p in ('first aid', 'primeiros socorros', 'primeros auxilios')):
        score += 60
    elif leaf in ('treatment', 'management', 'tratamento', 'tratamiento', 'what to do'):
        score += 35
    elif leaf in concepts and any(p in heading for p in ('treatment', 'management', 'tratamento', 'tratamiento')):
        score += 45
    if plan.scope.get('age_group') == 'infant' and any(p in leaf for p in ('infant', 'babies', 'bebe', 'lactante')):
        score += 45
    if plan.scope.get('consciousness') == 'unresponsive' and any(p in leaf for p in ('unconscious', 'unresponsive', 'inconsciente')):
        score += 45
    return score


def _local_topic_evidence(source, plan):
    # Local headings need not repeat the short phrases sent to library search.
    label = normalize(source['section'] + ' ' + source['doc_title'])
    personal = source.get('doc_id', '').startswith('extra/')
    if not personal and _local_domain_mismatch(source, plan):
        return False
    label_topics = set(matching_topics(label))
    if label_topics.intersection(plan.topics) or _topic_evidence(label, plan):
        return True
    # A guide about a different emergency may mention this one as a symptom.
    if label_topics and not personal:
        return False
    body = normalize(source['text'])
    return bool(set(matching_topics(body)).intersection(plan.topics)) or _topic_evidence(body, plan)


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
    direct_title = normalize(source.get('title', source.get('doc_title', ''))) if actionable else ''
    if not has_topic_evidence(body, plan.topics, plan.question + ' ' + ' '.join(plan.context_terms), direct_title):
        return False
    if source.get('kind') == 'kit':
        return _local_topic_evidence(source, plan)
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
    if _educational_page(source, plan) or inapplicability_reason(source, plan):
        return 0
    if not plan.topics and not _general_relevance(source, plan):
        return 0
    title = source.get('title', source.get('doc_title', ''))
    heading = source.get('section', '')
    text = source.get('text', source.get('snippet', ''))
    label = normalize(title + ' ' + heading)
    body = normalize(text)
    question_context = normalize(plan.question + ' ' + ' '.join(plan.context_terms))
    special_conditions = (
        ('cement', 'cimento', 'cemento'), ('tar', 'asfalto'),
        ('malnutrition', 'desnutricao', 'desnutricion'),
        ('childbirth', 'parto', 'postpartum', 'pos parto'),
        ('fever', 'febrile', 'febre', 'fiebre'),
        ('previous stroke', 'prior stroke', 'avc anterior'),
    )
    if plan.topics and any(any(re.search(r'\b' + re.escape(term) + r'\b', label) for term in group)
                           and not any(re.search(r'\b' + re.escape(term) + r'\b', question_context) for term in group)
                           for group in special_conditions):
        return 0
    if plan.topics and any(term in label and term not in normalize(plan.question) for term in ('fukushima', 'nuclear', 'radioactive')):
        return 0
    heading_topics = set(matching_topics(normalize(heading)))
    if plan.topics and heading_topics and not heading_topics.intersection(plan.topics):
        return 0
    if plan.topics and (_BACKGROUND.search(label) or _SPECIALIST.search(normalize(heading))):
        return 0
    if plan.scope.get('consciousness') == 'unresponsive' and re.search(r'\b(by mouth|oral intake|oral glucose|via oral|por boca)\b', normalize(heading)):
        return 0
    if plan.topics and re.search(r'\b(intravenous|thrombolysis|thrombectomy|craniectomy|neurosurgical|intubation)\b', body) and not re.search(r'\b(call|emergency services|first aid|cardiopulmonary resuscitation|cpr|cool|back blows|direct pressure|protect|do not|never|auto injector|epipen)\b', body):
        return 0
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
    if not age and len(scoped) == 1:
        return 0
    if age and scoped and age not in scoped:
        return 0
    if 'neonatal' in scoped and age == 'infant' and 'infant' not in scoped:
        return 0
    queries = [plan.question, ' '.join(plan.context_terms)]
    queries += [q for values in plan.queries_by_language.values() for q in values]
    queries = [q for q in queries if q]
    if not any(is_relevant(q, title + '\n' + heading + '\n' + text) for q in queries):
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
    return score + _section_priority(source, plan) if plan.topics else score or .1


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
    selected, seen = [], set()
    for candidates, limit in ((local, local_limit), (library, library_limit)):
        count = 0
        for source in candidates:
            if count >= max(0, limit):
                break
            # Keep quantities and punctuation: 1.0 must never collapse into 10.
            key = ' '.join(source.get('text', '').split())
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            selected.append(source)
            count += 1
    protected = selected[:1] if local_limit > 0 and local else []
    remaining = sorted(selected[len(protected):], key=lambda s: s['retrieval_score'], reverse=True)
    return protected + remaining
