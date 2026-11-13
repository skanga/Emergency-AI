"""Kiwix server integration (kiwix-serve or the Kiwix Desktop "Local Kiwix Server").

Use the public full-text search API: /search?pattern=...&format=xml
and download article content as context for the AI.
"""

import html
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .config import CONFIG_DIR, load_json
from .net import get_text, is_up

LANG3 = {"pt": "por", "en": "eng", "es": "spa"}


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "sup"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "br", "tr", "section", "dd", "dt", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        t = "".join(self.parts)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n\n", t)
        return t.strip()


def html_to_text(raw):
    p = _TextExtractor()
    try:
        p.feed(raw)
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw)
    return p.text()


class KiwixClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self._books = None

    def available(self):
        return is_up(self.base_url + "/catalog/v2/entries?count=1", timeout=1.5)

    def local_link(self, link):
        """Normalize same-service links; never fetch arbitrary search-result URLs."""
        if not link:
            return None
        base = urllib.parse.urlsplit(self.base_url)
        url = urllib.parse.urlsplit(urllib.parse.urljoin(self.base_url + "/", link))
        if (url.scheme, url.netloc) != (base.scheme, base.netloc):
            return None
        return urllib.parse.urlunsplit(("", "", url.path, url.query, url.fragment))

    def books(self):
        """List served books (ZIMs): [{name, title, lang}]."""
        if self._books is not None:
            return self._books
        books = []
        try:
            xml = get_text(self.base_url + "/catalog/v2/entries?count=-1", timeout=5)
            root = ET.fromstring(xml)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            archives = load_json(os.path.join(CONFIG_DIR, "zims.json"), {}).get("archives", [])
            for entry in root.findall("a:entry", ns):
                name = (entry.findtext("a:name", default="", namespaces=ns) or "").strip()
                title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
                lang = (entry.findtext("a:language", default="", namespaces=ns) or "").strip()
                if name:
                    title = title or name
                    if any(name == a["name"] or name.startswith(a["name"] + "_") for a in archives):
                        date = re.search(r"_(\d{4}-\d{2})(?:\.zim)?$", name)
                        if not date:
                            issued = entry.findtext("{http://purl.org/dc/terms/}issued", default="").strip()
                            date = re.match(r"(\d{4}-(?:0[1-9]|1[0-2]))(?:-\d{2})?(?:T.*)?$", issued)
                        label = "ARCHIVED " + date[1] if date else "ARCHIVED; snapshot date unknown"
                        title += f" [{label}; may be outdated]"
                    books.append({"name": name, "title": title, "lang": lang})
        except Exception:
            pass
        self._books = books
        return books

    def search(self, query, lang="en", limit=3):
        """Search all ZIMs. Prefer the requested language, then English."""
        books = self.books()
        if not books:
            return []
        want = LANG3.get(lang, lang)
        ordered = [b for b in books if want in b["lang"]] + [b for b in books if want not in b["lang"]]
        results = []
        # Query each book (up to 6) to avoid relying on global relevance ordering.
        for book in ordered[:6]:
            if len(results) >= limit * 2:
                break
            params = urllib.parse.urlencode({
                "pattern": query, "books.name": book["name"], "format": "xml", "pageLength": 2,
            })
            try:
                xml = get_text(f"{self.base_url}/search?{params}", timeout=6)
                root = ET.fromstring(xml)
            except Exception:
                continue
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = self.local_link((item.findtext("link") or "").strip())
                desc = html_to_text(html.unescape(item.findtext("description") or ""))
                if title and link:
                    results.append({"title": title, "link": link, "snippet": desc,
                                    "book": book["title"], "book_name": book["name"]})
        return results[:limit]

    def article_text(self, link, max_chars=20000):
        link = self.local_link(link)
        if not link:
            return ""
        url = urllib.parse.urljoin(self.base_url + "/", link)
        try:
            raw = get_text(url, timeout=8)
        except Exception:
            return ""
        text = html_to_text(raw)
        return text if len(text) <= max_chars else ""
