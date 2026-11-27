"""Answer engine: retrieve kit guides and Kiwix articles (RAG), then generate an answer with the local model."""

import threading
import time
import re

from . import i18n
from .answer_validation import PROMPT as VALIDATION_PROMPT, source_for_prompt, validate_answer
from .kiwix import KiwixClient
from .knowledge import KnowledgeBase, is_relevant, strip_accents, tokenize
from .llm import LLMError, detect_llm
from .query_planner import plan_query
from . import retrieval
from .source_policy import evaluate_conflicts, source_version
from .guidance import guidance_sources, fallback_answer


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
        guidance = guidance_sources(plan, lang)
        candidates = local + guidance + library
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
        # Preserve the first applicable local guide, then add complete scoped
        # guidance. This is context ordering, not source-authority precedence.
        first_local = sources[:1] if sources and sources[0]['kind'] == 'kit' else []
        sources = first_local + [s for s in guidance if s['id'] not in superseded] + sources[len(first_local):]
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
                      local_candidates=len(local), library_passages=len(library), guidance_candidates=len(guidance))
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
            label = (i18n.GUIDANCE_LABEL[lang] if s['kind'] == 'guidance' else
                     i18n.KIT_LABEL[lang] if s["kind"] == "kit" else i18n.KIWIX_LABEL[lang])
            lines.append(f"[S{s['n']}] {label}: {s['doc_title']} — {s['section']}\n{source_for_prompt(s['text'])}")
        ctx = "\n\n".join(lines) if lines else "(—)"
        user = f"{i18n.SOURCES_HEADER[lang]}:\n{ctx}\n\n{i18n.QUESTION_HEADER[lang]}: {question}"
        prompt = i18n.SYSTEM_PROMPT[lang] if lines else i18n.general_knowledge_prompt(lang)
        messages = [{"role": "system", "content": prompt + VALIDATION_PROMPT}]
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
        def result(messages, fitted, count):
            return messages, fitted, {'input_tokens': count, 'history_omitted': dropped_history,
                                     'included_source_ids': [s.get('id', s['n']) for s in fitted if not s.get('context_omitted')],
                                     'sources_omitted': [s['n'] for s in fitted if s.get('context_omitted')]}

        # There are at most two old conversation pairs. Keep their precedence
        # over evidence unchanged, and avoid searching when the prompt fits.
        while True:
            messages = self.build_messages(question, lang, sources, history)
            count = llm.count_prompt(messages)
            if count <= budget:
                return result(messages, sources, count)
            if not history:
                break
            history = history[2:]
            dropped_history = True

        included = [i for i, source in enumerate(sources) if not source.get('context_omitted')]

        def candidate(keep):
            fitted = [dict(source) for source in sources]
            for index in included[keep:]:
                source = fitted[index]
                source.setdefault('original_text', source['text'])
                source.update(context_omitted=True, context_omitted_reason='token_budget',
                              text=i18n.READ_FULL_SOURCE[lang])
            messages = self.build_messages(question, lang, fitted)
            return messages, fitted, llm.count_prompt(messages)

        # Search complete evidence prefixes. Every accepted candidate is counted
        # by the backend; no estimated token count can authorize generation.
        # Token boundaries can be non-monotonic, so this finds a verified fitting
        # prefix rather than promising the globally largest possible prefix.
        low, high = 1, len(included) - 1
        best = None
        while low <= high:
            keep = (low + high) // 2
            trial = candidate(keep)
            if trial[2] <= budget:
                best = trial
                low = keep + 1
            else:
                high = keep - 1
        if best is not None:
            return result(*best)

        # Zero sources changes the system prompt. Count it separately rather
        # than assuming that it is smaller than a prompt containing evidence.
        if included:
            trial = candidate(0)
            if trial[2] <= budget:
                return result(*trial)
        raise LLMError('The question exceeds the available input context budget')

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
            text = source_for_prompt(s["text"])
            parts.append(f"### [{s['n']}] {s['doc_title']} › {s['section']}\n\n{text}\n")
        return "\n".join(parts)

    @staticmethod
    def _fallback(sources, lang, conflicts, question, history):
        """Revalidate a catalog composition independently of any generated draft."""
        text, meta = fallback_answer(sources, lang, conflicts)
        if not text:
            return '', sources, meta
        used = set(meta['used_source_ids'])
        restored = []
        for source in sources:
            source = dict(source)
            if source['id'] in used:
                source['fallback_evidence'] = True
                source['model_context_omitted'] = bool(source.get('context_omitted'))
                if source.get('context_omitted'):
                    source.update(text=source['original_text'], context_omitted=False,
                                  context_omitted_reason=None)
            restored.append(source)
        rendered, validation = validate_answer(re.sub(r'\[(\d+)\]', r'[S\1]', text),
                                               restored, question, lang, history)
        meta['validation'] = validation
        if not rendered:
            meta.update(status='blocked', used_source_ids=[], fallback_evidence_ids=[])
            return '', sources, meta
        return i18n.GUIDANCE_FALLBACK[lang] + rendered, restored, meta

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
        fallback = {}
        need_fallback = False
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
            chunks = []
            failed = False
            oversized = False
            size = 0
            try:
                stream = llm.stream_chat(messages, generation)
                for tok in stream:
                    size += len(tok)
                    if size > 131072:
                        oversized = True
                        if hasattr(stream, 'close'):
                            stream.close()
                        break
                    chunks.append(tok)
            except (LLMError, OSError) as e:
                generation.update(incomplete=True, finish_reason='error')
                self._llm_checked = 0
                failed = True
                yield "token", i18n.LLM_ERROR[lang].format(err=str(e)[:120])
            if generation.get('incomplete'):
                key = 'limit' if generation.get('finish_reason') == 'length' else 'interrupted'
                yield 'token', i18n.INCOMPLETE_ANSWER[lang][key] + '\n\n'
            if oversized:
                generation.update(incomplete=True, finish_reason='validation_limit',
                                  validation={'status':'blocked', 'issues':['answer_size_limit'], 'claim_support':'not_verified'})
                mode, reason = 'search', 'answer_validation_failed'
                yield 'token', i18n.ANSWER_WITHHELD[lang]
                need_fallback = True
            elif failed or generation.get('incomplete') or not ''.join(chunks).strip():
                generation['validation'] = {'status':'not_run', 'issues':['generation_incomplete'],
                                             'claim_support':'not_verified'}
                mode, reason = 'search', 'generation_failed'
                need_fallback = True
            else:
                rendered, validation = validate_answer(''.join(chunks), sources, question, lang, history)
                generation['validation'] = validation
                if validation['status'] == 'blocked':
                    mode, reason = 'search', 'answer_validation_failed'
                    yield 'token', i18n.ANSWER_WITHHELD[lang]
                    need_fallback = True
                else:
                    yield 'token', rendered
        elif use_llm:
            need_fallback = True
        elif not blocked and not reviewed_omitted:
            yield "token", self.extractive_answer(lang, sources, model_unavailable=model_unavailable)
        if need_fallback:
            help_text, fallback_sources, fallback = self._fallback(sources, lang, conflicts, question, history)
            if help_text:
                sources = fallback_sources
                mode = 'fallback'
                # Original generation/retrieval metadata still describes only
                # model input. These sources are explicitly fallback evidence.
                yield 'sources', sources
                yield 'token', help_text
            elif reason in ('model_unavailable', 'generation_failed'):
                yield 'token', self.extractive_answer(lang, sources, model_unavailable=model_unavailable)
        if self.is_medical(question):
            yield "token", i18n.MEDICAL_FOOTER[lang]
        yield "done", {"mode": mode, "seconds": round(time.time() - t0, 1),
                       "llm": llm.describe() if llm else None, "generation": generation,
                       "sources_supplied": sources_supplied, "reason": reason, "retrieval": report,
                       "fallback": fallback}

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
