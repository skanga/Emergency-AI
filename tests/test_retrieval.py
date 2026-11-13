"""Preserve complete source sections and resolve installed model tags."""

import unittest
from unittest.mock import Mock, patch

from app.engine import Engine
from app.knowledge import Chunk, split_markdown
from app.kiwix import html_to_text
from app.llm import Ollama


class RetrievalTests(unittest.TestCase):
    def test_large_section_keeps_warning_and_source_with_steps(self):
        body = "1. A complete step.\n\n" * 200 + "Warning: read every step.\n\n> Source: example.org"
        _, sections = split_markdown("# Guide\n\n## Procedure\n\n" + body)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0][2], body)

    def test_extractive_answer_does_not_cut_off_a_step(self):
        engine = Engine({"llm_backend": "none", "kiwix_enabled": False})
        body = "step " * 400 + "FINAL WARNING AND SOURCE"
        answer = engine.extractive_answer("en", [{"n": 1, "doc_title": "Guide", "section": "Procedure", "text": body}])
        self.assertIn(body, answer)

    def test_oversized_source_links_to_full_text_without_partial_steps(self):
        engine = Engine({"llm_backend": "none", "kiwix_enabled": False, "context_chars": 500})
        body = "incomplete instruction " * 100
        chunk = Chunk("id", "en", "guide", "Guide", "Procedure", "procedure", body)
        engine.kb.search = Mock(return_value=[(1, chunk)])
        sources = engine.retrieve("instruction", "en")
        self.assertTrue(sources)
        self.assertNotIn("incomplete instruction", sources[0]["text"])
        self.assertTrue(sources[0].get("context_omitted"))
        self.assertIn("full", engine.extractive_answer("en", sources).lower())

    def test_html_tables_are_not_silently_discarded(self):
        text = html_to_text("<table><tr><th>Name</th><th>Amount</th></tr><tr><td>Water</td><td>1 litre</td></tr></table>")
        self.assertIn("Water", text)
        self.assertIn("1 litre", text)
        self.assertNotIn("Water1", text)


class OllamaTests(unittest.TestCase):
    def test_missing_explicit_tag_is_unavailable(self):
        client = Ollama("http://localhost:11434", "qwen2.5:3b")
        with patch("app.llm.get_json", return_value={"models": [{"name": "qwen2.5:7b"}]}):
            self.assertFalse(client.available())
        self.assertEqual(client.model, "qwen2.5:3b")

    def test_untagged_model_resolves_latest_only(self):
        client = Ollama("http://localhost:11434", "qwen2.5")
        with patch("app.llm.get_json", return_value={"models": [{"name": "qwen2.5:latest"}]}):
            self.assertTrue(client.available())
        self.assertEqual(client.model, "qwen2.5:latest")
