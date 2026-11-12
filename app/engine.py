"""Answer engine: retrieve kit guides and Kiwix articles (RAG), then generate an answer with the local model."""

import threading
import time

from . import i18n
from .kiwix import KiwixClient
from .knowledge import KnowledgeBase, best_passages, strip_accents, tokenize
from .llm import LLMError, detect_llm


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
        llm = self.llm(force=True)
        kiwix_ok = self.kiwix_ok(force=True)
        return {
            "llm": llm.describe() if llm else None,
            "kiwix": {"url": self.kiwix.base_url, "books": self.kiwix.books()} if kiwix_ok else None,
            "knowledge": self.kb.stats(),
        }

    # ---------- retrieval ----------
    def retrieve(self, question, lang, history=None, use_kiwix=True):
        query = question
        if history and len(tokenize(question)) < 4:
            prev = [h.get("content", "") for h in history if h.get("role") == "user"]
            if prev:
                query = prev[-1] + " " + question
        k = int(self.settings.get("search_results", 5))
        sources = []
        for score, ch in self.kb.search(query, lang, k=k):
            d = ch.to_dict(score=score)
            sources.append(d)
        if use_kiwix and self.kiwix_ok():
            try:
                for r in self.kiwix.search(question, lang, limit=int(self.settings.get("kiwix_results", 3))):
                    text = self.kiwix.article_text(r["link"])
                    passage = best_passages(text, query, max_chars=1500) if text else r["snippet"]
                    sources.append({
                        "kind": "kiwix", "doc_title": r["book"], "section": r["title"],
                        "link": r["link"], "text": passage, "book_name": r["book_name"],
                    })
            except Exception:
                pass
        # Number and trim sources to fit the model context.
        budget = int(self.settings.get("context_chars", 7000))
        out = []
        for s in sources:
            text = s["text"]
            if budget <= 300:
                break
            if len(text) > budget:
                text = text[:budget].rsplit(" ", 1)[0] + " …"
            budget -= len(text)
            s = dict(s, text=text, n=len(out) + 1)
            out.append(s)
        return out

    # ---------- generation ----------
    @staticmethod
    def is_medical(text):
        t = strip_accents(text.lower())
        return any(w in t for w in i18n.MEDICAL_WORDS)

    def build_messages(self, question, lang, sources, history=None):
        lines = []
        for s in sources:
            label = i18n.KIT_LABEL[lang] if s["kind"] == "kit" else i18n.KIWIX_LABEL[lang]
            lines.append(f"[{s['n']}] {label}: {s['doc_title']} — {s['section']}\n{s['text']}")
        ctx = "\n\n".join(lines) if lines else "(—)"
        user = f"{i18n.SOURCES_HEADER[lang]}:\n{ctx}\n\n{i18n.QUESTION_HEADER[lang]}: {question}"
        messages = [{"role": "system", "content": i18n.SYSTEM_PROMPT[lang]}]
        for h in (history or [])[-4:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"][:1500]})
        messages.append({"role": "user", "content": user})
        return messages

    def extractive_answer(self, lang, sources):
        if not sources:
            return i18n.NO_RESULTS[lang]
        parts = [i18n.NO_LLM_NOTE[lang], ""]
        for s in sources[:3]:
            text = s["text"]
            if len(text) > 1600:
                text = text[:1600].rsplit(" ", 1)[0] + " …"
            parts.append(f"### [{s['n']}] {s['doc_title']} › {s['section']}\n\n{text}\n")
        return "\n".join(parts)

    def answer(self, question, lang="en", history=None, use_kiwix=True, use_llm=True):
        """Event generator: ('sources', [...]), ('token', str), ('done', {...})."""
        lang = lang if lang in i18n.SYSTEM_PROMPT else "en"
        t0 = time.time()
        sources = self.retrieve(question, lang, history, use_kiwix)
        yield "sources", sources
        llm = self.llm() if use_llm else None
        mode = "llm" if llm else "search"
        if llm:
            messages = self.build_messages(question, lang, sources, history)
            got = False
            try:
                for tok in llm.stream_chat(messages):
                    got = True
                    yield "token", tok
            except (LLMError, OSError) as e:
                self._llm_checked = 0
                yield "token", i18n.LLM_ERROR[lang].format(err=str(e)[:120])
                yield "token", self.extractive_answer(lang, sources)
                mode = "search"
            if not got and mode == "llm":
                yield "token", self.extractive_answer(lang, sources)
                mode = "search"
        else:
            yield "token", self.extractive_answer(lang, sources)
        if self.is_medical(question):
            yield "token", i18n.MEDICAL_FOOTER[lang]
        yield "done", {"mode": mode, "seconds": round(time.time() - t0, 1),
                       "llm": llm.describe() if llm else None}

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
