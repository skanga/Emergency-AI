"""Tests: python -m unittest discover -s tests"""

import json
import os
import sys
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import LANGS  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.knowledge import KnowledgeBase, split_markdown, tokenize  # noqa: E402
from app.server import serve  # noqa: E402
import mock_servers  # noqa: E402

LLM_PORT, KIWIX_PORT, WEB_PORT = 18091, 18092, 18090


class KnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def test_same_guides_in_all_languages(self):
        ids = {lang: [d["id"] for d in self.kb.list_docs(lang) if not d["extra"]] for lang in LANGS}
        self.assertGreaterEqual(len(ids["pt"]), 15)
        self.assertEqual(ids["pt"], ids["en"])
        self.assertEqual(ids["pt"], ids["es"])

    def test_every_medical_section_cites_source(self):
        for lang, word in (("pt", "Fonte"), ("en", "Source"), ("es", "Fuente")):
            md = self.kb.get_doc(lang, "07-first-aid-medicine")
            doc_title, sections = split_markdown(md)
            for title, _, text in sections:
                # The introduction (disclaimer) and kit list are not clinical guidance.
                if title == doc_title or any(w in title.lower() for w in ("kit", "botiqu")):
                    continue
                self.assertIn(word, text, f"{lang}: section missing a source: {title}")

    def test_tokenize_accents(self):
        self.assertEqual(tokenize("Água"), tokenize("agua"))

    def test_search_relevance(self):
        cases = [
            ("pt", "como parar sangramento grave", "07-first-aid-medicine"),
            ("pt", "fazer fogo sem fósforo", "02-fire"),
            ("pt", "purificar água", "01-water"),
            ("pt", "fazer álcool 70%", "09-alcohol"),
            ("en", "how to purify water", "01-water"),
            ("en", "snake bite", "07-first-aid-medicine"),
            ("es", "cómo hacer jabón", "08-hygiene-sanitation"),
            ("es", "conservar carne sin refrigerador", "04-food"),
        ]
        for lang, q, doc in cases:
            res = self.kb.search(q, lang, k=3)
            self.assertTrue(res, q)
            self.assertIn(doc, [c.doc_id for _, c in res], f"{lang}: {q}")


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.llm = mock_servers.start(mock_servers.LLMHandler, LLM_PORT)
        cls.kiwix = mock_servers.start(mock_servers.KiwixHandler, KIWIX_PORT)

    @classmethod
    def tearDownClass(cls):
        cls.llm.shutdown()
        cls.kiwix.shutdown()
        cls.llm.server_close()
        cls.kiwix.server_close()

    def settings(self, **kw):
        s = {"llm_backend": "openai", "llm_url": f"http://127.0.0.1:{LLM_PORT}/v1",
             "kiwix_url": f"http://127.0.0.1:{KIWIX_PORT}", "kiwix_enabled": True}
        s.update(kw)
        return s

    def test_search_only_mode(self):
        eng = Engine(self.settings(llm_backend="none", kiwix_enabled=False))
        text, sources, info = eng.answer_text("como fazer soro caseiro", "pt")
        self.assertEqual(info["mode"], "search")
        self.assertIn("açúcar", text)
        self.assertTrue(sources)

    def test_llm_with_kiwix(self):
        eng = Engine(self.settings())
        text, sources, info = eng.answer_text("desidratação por diarreia", "pt")
        self.assertEqual(info["mode"], "llm")
        self.assertIn("Ferva a água", text)
        self.assertIn("⚠️", text)  # medical disclaimer
        kinds = {s["kind"] for s in sources}
        self.assertEqual(kinds, {"kit", "kiwix"})
        kiwix_src = [s for s in sources if s["kind"] == "kiwix"][0]
        self.assertIn("reidratação oral", kiwix_src["text"])
        self.assertNotIn("var x", kiwix_src["text"])
        prompt = mock_servers.LLMHandler.last_request["messages"][-1]["content"]
        self.assertIn("[1]", prompt)
        self.assertIn("FONTES", prompt)

    def test_llm_down_falls_back(self):
        eng = Engine(self.settings(llm_url="http://127.0.0.1:1/v1", kiwix_enabled=False))
        text, _, info = eng.answer_text("how to make fire", "en")
        self.assertEqual(info["mode"], "search")
        self.assertIn("Search-only mode", text)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings = {"llm_backend": "none", "kiwix_enabled": False}
        cls.httpd = serve(Engine(settings), settings, "127.0.0.1", WEB_PORT)
        import threading
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{WEB_PORT}{path}", timeout=5) as r:
            return r.read().decode()

    def test_pages_and_api(self):
        self.assertIn("Emergency AI", self.get("/"))
        self.assertIn('<html lang="en">', self.get("/"))
        self.assertIn("function", self.get("/app.js"))
        guides = json.loads(self.get("/api/guides?lang=es"))
        self.assertEqual(len([g for g in guides if not g["extra"]]), 15)
        doc = json.loads(self.get("/api/guide?lang=en&id=01-water"))
        self.assertTrue(doc["markdown"].startswith("# "))
        st = json.loads(self.get("/api/status"))
        self.assertIsNone(st["llm"])
        self.assertEqual(st["language"], "en")
        for path in ("/api/guides", "/api/guides?lang=unknown"):
            guides = json.loads(self.get(path))
            self.assertIn("Water", next(g["title"] for g in guides if g["id"] == "01-water"))

    def test_path_traversal_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.get("/../config/settings.json")
        self.assertEqual(error.exception.code, 404)
        error.exception.close()

    def test_ask_stream(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f"http://127.0.0.1:{WEB_PORT}/api/ask",
                                     data=json.dumps({"q": "como fazer fogo", "lang": "pt"}).encode(),
                                     headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=10) as r:
            body = r.read().decode()
        self.assertIn("event: sources", body)
        self.assertIn("event: token", body)
        self.assertIn("event: done", body)


if __name__ == "__main__":
    unittest.main()
