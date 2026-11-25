"""Answer engine: retrieve kit guides and Kiwix articles (RAG), then generate an answer with the local model."""

import threading
import time

from . import i18n
from .kiwix import KiwixClient
from .knowledge import KnowledgeBase, is_relevant, strip_accents, tokenize
from .llm import LLMError, detect_llm
from .query_planner import plan_query
from . import retrieval
from .source_policy import evaluate_conflicts, source_version


class Engine:
    def __init__(self, settings):
        self.settings = settings
        self.kb = KnowledgeBase()
        self.kiwix = KiwixClient(settings.get("kiwix_url", "http://127.0.0.1:8092"))
        self._llm = None
        self._llm_checked = 0
        self._kiwix_ok = False
        self._kiwix_checked = 0
        self._lock = threading.Lock()

    # ---------- availability (briefly cached) ----------
    def reset_llm(self):
        with self._lock:
            self._llm = None
            self._llm_checked = 0

    def llm(self, force=False):
        with self._lock:
            if force or time.time() - self._llm_checked > 15:
                self._llm = detect_llm(self.settings)
                self._llm_checked = time.time()
            return self._llm

    def kiwix_ok(self, force=False):
        if not self.settings.get("kiwix_enabled", True):
            return False
        with self._lock:
            if force or time.time() - self._kiwix_checked > 15:
                self._kiwix_ok = self.kiwix.available()
                if self._kiwix_ok:
                    self.kiwix._books = None
                self._kiwix_checked = time.time()
            return self._kiwix_ok

    def status(self):
        from pathlib import Path
        from .document_index import DocumentIndex, document_state
        llm = self.llm(force=True)
        kiwix_ok = self.kiwix_ok(force=True)
        books = []
        if kiwix_ok:
            index = DocumentIndex(self.settings.get('document_index_dir', Path(__file__).resolve().parent.parent / 'indexes'))
            books = [dict(book, capabilities={'catalog_reachable': True, 'native_search': 'not_checked',
                                             'documents': document_state(book, index)}) for book in self.kiwix.books()]
        return {
            "llm": llm.describe() if llm else None,
            "kiwix": {"url": self.kiwix.base_url, "books": books} if kiwix_ok else None,
            "knowledge": self.kb.stats(),
        }

    # ---------- retrieval ----------
    def retrieve(self, question, lang, history=None, use_kiwix=True, kiwix_books=None, diagnostics=None):
        deadline = time.monotonic() + retrieval.REQUEST_SECONDS
        report = diagnostics if diagnostics is not None else {}
        report.clear()
        plan = plan_query(question, lang, history)
        report.update(topics=list(plan.topics), scope=plan.scope, limited_cross_language=plan.limited_cross_language,
                      libraries=[], fetches=[], searches=0, fetched=0, candidates=0)
        local_limit = max(0, int(self.settings.get('search_results', 5)))
        library_limit = max(0, int(self.settings.get('kiwix_results', 3)))
        local = retrieval.local_sources(self.kb, plan, lang, local_limit)
        library = []
        if not use_kiwix or not self.settings.get('kiwix_enabled', True):
            report['status'] = 'disabled'
        elif kiwix_books == []:
            report['status'] = 'no_selection'
        else:
            try:
                library = retrieval.library_sources(self.kiwix, plan, kiwix_books, report, deadline,
                                                    self.settings.get('document_index_dir'))
            except (OSError, TimeoutError) as exc:
                report.update(status='failed', error=str(exc))
        # Aliased search results can point to the same passage. Keep one
        # reference and one prompt inclusion for each stable source identity.
        unique = {}
        for source in local + library:
            unique.setdefault(source['id'], source)
        local = [s for s in unique.values() if s['kind'] == 'kit']
        library = [s for s in unique.values() if s['kind'] != 'kit']
        candidates = local + library
        try:
            conflicts = evaluate_conflicts(candidates, plan.topics, plan.scope)
        except (ValueError, OSError) as exc:
            # A broken policy must not silently disable reviewed safety decisions.
            conflicts = [dict(id='source-policy-error', topic='policy', scope=dict(plan.scope),
                              source_ids=[s['id'] for s in candidates],
                              versions={s['id']: source_version(s) for s in candidates},
                              detection_basis='policy_error', resolution='unresolved',
                              explanation=str(exc))]
        report['conflicts'] = conflicts
        unresolved = any(c['resolution'] == 'unresolved' for c in conflicts)
        superseded = {sid for c in conflicts if c['resolution'] == 'reviewed_precedence'
                      for sid in c['source_ids'] if sid != c['preferred_source']}
        preferred = {c['preferred_source'] for c in conflicts if c['resolution'] == 'reviewed_precedence'}
        sources = retrieval.select_sources([s for s in local if s['id'] not in superseded],
                                           [s for s in library if s['id'] not in superseded],
                                           local_limit, library_limit)
        # Reviewed choices and both sides of a disagreement remain inspectable
        # even when their retrieval rank falls outside the presentation caps.
        referenced = {sid for c in conflicts for sid in c['source_ids']}
        selected = {s['id'] for s in sources}
        sources += [s for s in candidates if s['id'] in referenced and s['id'] not in selected]
        sources.sort(key=lambda s: s['id'] not in preferred)
        budget = max(0, int(self.settings.get('context_chars', 7000)))
        out = []
        for source in sources:
            original = source['text']
            if unresolved:
                reason = 'conflict_unresolved'
            elif source['id'] in superseded:
                reason = 'reviewed_precedence'
            else:
                reason = 'empty_content' if not original else ('context_budget' if len(original) > budget else None)
            if not reason:
                budget -= len(original)
            out.append(dict(source, original_text=original,
                            text=i18n.READ_FULL_SOURCE[lang] if reason else original,
                            source_version=source_version(source), n=len(out) + 1,
                            conflicts=[c for c in conflicts if source['id'] in c['source_ids']],
                            context_omitted=bool(reason), context_omitted_reason=reason))
        report.update(included=sum(not s['context_omitted'] for s in out), selected=len(out),
                      local_candidates=len(local), library_passages=len(library))
        return out

    # ---------- generation ----------
    @staticmethod
    def is_medical(text):
        t = strip_accents(text.lower())
        return any(w in t for w in i18n.MEDICAL_WORDS)

    def build_messages(self, question, lang, sources, history=None):
        lines = []
        for s in sources:
            if s.get("context_omitted"):
                continue
            label = i18n.KIT_LABEL[lang] if s["kind"] == "kit" else i18n.KIWIX_LABEL[lang]
            lines.append(f"[{s['n']}] {label}: {s['doc_title']} — {s['section']}\n{s['text']}")
        ctx = "\n\n".join(lines) if lines else "(—)"
        user = f"{i18n.SOURCES_HEADER[lang]}:\n{ctx}\n\n{i18n.QUESTION_HEADER[lang]}: {question}"
        prompt = i18n.SYSTEM_PROMPT[lang] if lines else i18n.general_knowledge_prompt(lang)
        messages = [{"role": "system", "content": prompt}]
        for h in (history or [])[-4:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user})
        return messages

    def fit_messages(self, llm, question, lang, sources, history=None):
        """Reserve generation space; omit old turns, then whole source sections."""
        options = llm.options()
        budget = options['context'] - options['max_tokens'] - options['context_margin']
        history = list(history or [])[-4:]
        sources = [dict(s) for s in sources]
        dropped_history = False
        while True:
            messages = self.build_messages(question, lang, sources, history)
            count = llm.count_prompt(messages)
            if count <= budget:
                return messages, sources, {'input_tokens': count, 'history_omitted': dropped_history,
                                          'included_source_ids': [s.get('id', s['n']) for s in sources if not s.get('context_omitted')],
                                          'sources_omitted': [s['n'] for s in sources if s.get('context_omitted')]}
            if history:
                history = history[2:]
                dropped_history = True
                continue
            included = [s for s in sources if not s.get('context_omitted')]
            if not included:
                raise LLMError('The question exceeds the available input context budget')
            included[-1].setdefault('original_text', included[-1]['text'])
            included[-1].update(context_omitted=True, context_omitted_reason='token_budget', text=i18n.READ_FULL_SOURCE[lang])

    def extractive_answer(self, lang, sources, model_unavailable=True):
        if not sources:
            return i18n.NO_RESULTS[lang]
        note = i18n.NO_LLM_NOTE if model_unavailable else i18n.SOURCE_FALLBACK_NOTE
        parts = [note[lang], ""]
        if all(s.get("context_omitted") for s in sources):
            return i18n.READ_FULL_SOURCE[lang]
        for s in sources:
            if s.get("context_omitted"):
                continue
            text = s["text"]
            parts.append(f"### [{s['n']}] {s['doc_title']} › {s['section']}\n\n{text}\n")
        return "\n".join(parts)

    def answer(self, question, lang="en", history=None, use_kiwix=True, use_llm=True, kiwix_books=None):
        """Event generator: ('sources', [...]), ('token', str), ('done', {...})."""
        lang = lang if lang in i18n.SYSTEM_PROMPT else "en"
        t0 = time.time()
        report = {}
        sources = self.retrieve(question, lang, history, use_kiwix, kiwix_books, diagnostics=report)
        conflicts = report.get('conflicts', [])
        blocked = any(c['resolution'] == 'unresolved' for c in conflicts)
        llm = self.llm() if use_llm and not blocked else None
        model_unavailable = llm is None
        reason = 'source_conflict' if blocked else ('ai_disabled' if not use_llm else ('model_unavailable' if llm is None else None))
        sources_supplied = False
        mode = "llm" if llm else "search"
        generation = {}
        fit_error = None
        if llm:
            try:
                messages, fitted, generation = self.fit_messages(llm, question, lang, sources, history)
                sources = fitted
                sources_supplied = any(not s.get('context_omitted') for s in sources)
            except (LLMError, OSError) as e:
                fit_error = i18n.LLM_ERROR[lang].format(err=str(e)[:120])
                llm, mode = None, 'search'
                reason = 'generation_failed'
        preferred = {c['preferred_source'] for c in conflicts if c['resolution'] == 'reviewed_precedence'}
        available = {s.get('id') for s in sources if not s.get('context_omitted')}
        reviewed_omitted = bool(preferred - available)
        if reviewed_omitted and not blocked:
            llm, mode, reason = None, 'search', 'reviewed_source_omitted'
            sources_supplied = False
        report['included_source_ids'] = [s.get('id', s['n']) for s in sources if not s.get('context_omitted')]
        report["included"] = sum(not s.get("context_omitted") for s in sources)
        yield "retrieval", report
        yield "sources", sources
        if blocked:
            notice = i18n.POLICY_UNAVAILABLE if any(c['detection_basis'] == 'policy_error' for c in conflicts) else i18n.CONFLICT_UNRESOLVED
            yield 'token', notice[lang]
        else:
            for conflict in conflicts:
                versions = ', '.join(f"{sid} ({version})" for sid, version in conflict['versions'].items())
                yield 'token', i18n.CONFLICT_REVIEWED[lang].format(
                    preferred=conflict['preferred_source'], versions=versions,
                    rationale=conflict['explanation'])
        if reviewed_omitted and not blocked:
            yield 'token', i18n.REVIEWED_SOURCE_OMITTED[lang]
        if fit_error:
            yield "token", fit_error
        if llm:
            note = i18n.SOURCES_SUPPLIED_NOTE if sources_supplied else i18n.UNGROUNDED_NOTE
            yield 'token', note[lang]
            got = False
            try:
                for tok in llm.stream_chat(messages, generation):
                    got = True
                    yield "token", tok
            except (LLMError, OSError) as e:
                generation.update(incomplete=True, finish_reason='error')
                self._llm_checked = 0
                yield "token", i18n.LLM_ERROR[lang].format(err=str(e)[:120])
                yield "token", self.extractive_answer(lang, sources, model_unavailable=False)
                mode = "search"
                reason = 'generation_failed'
            if generation.get('incomplete'):
                key = 'limit' if generation.get('finish_reason') == 'length' else 'interrupted'
                yield 'token', i18n.INCOMPLETE_ANSWER[lang][key] + '\n\n'
            if not got and mode == "llm":
                yield "token", self.extractive_answer(lang, sources, model_unavailable=False)
                mode = "search"
                reason = 'generation_failed'
        elif not blocked and not reviewed_omitted:
            yield "token", self.extractive_answer(lang, sources, model_unavailable=model_unavailable)
        if self.is_medical(question):
            yield "token", i18n.MEDICAL_FOOTER[lang]
        yield "done", {"mode": mode, "seconds": round(time.time() - t0, 1),
                       "llm": llm.describe() if llm else None, "generation": generation,
                       "sources_supplied": sources_supplied, "reason": reason, "retrieval": report}

    def answer_text(self, question, lang="en", **kw):
        text, sources, info = [], [], {}
        for kind, data in self.answer(question, lang, **kw):
            if kind == "sources":
                sources = data
            elif kind == "token":
                text.append(data)
            else:
                info = data
        return "".join(text), sources, info
