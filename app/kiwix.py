"""Kiwix server integration (kiwix-serve or the Kiwix Desktop "Local Kiwix Server").

Use the public full-text search API: /search?pattern=...&format=xml
and download article content as context for the AI.
"""

import html
from concurrent.futures import ThreadPoolExecutor
import os
import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .config import CONFIG_DIR, load_json
from .net import get_text, is_up
from .knowledge import tokenize

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
        self._catalog_error = None

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

    def _content_identity(self, href):
        """Read an archive root URL, rejecting foreign hosts and ambiguous paths."""
        try:
            raw = urllib.parse.urlsplit(href)
            decoded = urllib.parse.unquote(raw.path, errors="strict")
            if any(part in (".", "..") for part in decoded.split("/")):
                return None
            link = self.local_link(href)
            if not link or raw.query or raw.fragment:
                return None
            prefix = urllib.parse.urlsplit(self.base_url).path.rstrip("/")
            path = urllib.parse.urlsplit(link).path
            match = re.fullmatch(re.escape(prefix) + r"/content/([^/]+)/?", path)
            if not match:
                return None
            name = urllib.parse.unquote(match[1], errors="strict")
            if not name or any(c in name for c in "/\\%?#") or any(ord(c) < 32 for c in name):
                return None
            return name, link
        except (ValueError, UnicodeError):
            return None

    def books(self):
        """List logical selections with archive identity and publication metadata."""
        if self._books is not None:
            return self._books
        books = []
        try:
            xml = get_text(self.base_url + "/catalog/v2/entries?count=-1", timeout=5)
            root = ET.fromstring(xml)
            if root.tag != "{http://www.w3.org/2005/Atom}feed":
                raise ET.ParseError("Expected Atom catalog response")
            ns = {"a": "http://www.w3.org/2005/Atom"}
            archives = load_json(os.path.join(CONFIG_DIR, "zims.json"), {}).get("archives", [])
            for entry in root.findall("a:entry", ns):
                name = (entry.findtext("a:name", default="", namespaces=ns) or "").strip()
                title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
                lang = (entry.findtext("a:language", default="", namespaces=ns) or "").strip()
                if name:
                    issued = entry.findtext("{http://purl.org/dc/terms/}issued", default="").strip()
                    archive_uuid = entry.findtext("a:id", default="", namespaces=ns).removeprefix("urn:uuid:")
                    links = [link.get("href", "") for link in entry.findall("a:link", ns)
                             if link.get("type", "").split(";")[0].strip() == "text/html"]
                    identities = [self._content_identity(link) for link in links]
                    identity = identities[0] if identities and all(i == identities[0] for i in identities) else None
                    title = title or name
                    if any(name == a["name"] or name.startswith(a["name"] + "_") for a in archives):
                        date = re.search(r"_(\d{4}-\d{2})(?:\.zim)?$", name)
                        if not date:
                            issued = entry.findtext("{http://purl.org/dc/terms/}issued", default="").strip()
                            date = re.match(r"(\d{4}-(?:0[1-9]|1[0-2]))(?:-\d{2})?(?:T.*)?$", issued)
                        label = "ARCHIVED " + date[1] if date else "ARCHIVED; snapshot date unknown"
                        title += f" [{label}; may be outdated]"
                    books.append({"name": name, "title": title, "lang": lang,
                                  "archive_uuid": archive_uuid, "issued": issued,
                                  "served_name": identity[0] if identity else None,
                                  "content_url": identity[1] if identity else None,
                                  "identity_error": bool(links) and identity is None})
        except Exception as exc:
            self._catalog_error = str(exc) or type(exc).__name__
            return []
        self._catalog_error = None
        self._books = books
        return books

    def search(self, query, lang="en", limit=3, book_names=None, diagnostics=None):
        """Search logical selections (None = all editions, [] = none).

        Optional diagnostics is a caller-owned list of per-library outcomes;
        failures remain distinguishable from a successful search with zero hits.
        """
        if book_names == []:
            return []
        books = self.books()
        if self._catalog_error and diagnostics is not None:
            diagnostics.append({"status": "catalog_error", "error": self._catalog_error})
        if book_names is not None:
            selected = set(book_names)
            if diagnostics is not None:
                for name in sorted(selected - {book["name"] for book in books}):
                    diagnostics.append({"name": name, "status": "identity_error", "error": "Selection absent from catalog"})
            books = [book for book in books if book["name"] in selected]
        if not books:
            return []
        want = LANG3.get(lang, lang)
        ordered = [b for b in books if want in b["lang"]] + [b for b in books if want not in b["lang"]]
        def search_book(book):
            results = []
            served_name = book.get("served_name") or book["name"]
            diagnostic = {"name": book["name"], "served_name": book.get("served_name"),
                          "archive_uuid": book.get("archive_uuid", ""), "hits": 0}
            if book.get("identity_error"):
                diagnostic.update(status="identity_error", error="Invalid catalog content link")
                return results, diagnostic
            params = urllib.parse.urlencode({
                "pattern": query, "books.name": served_name, "format": "xml", "pageLength": 2,
            })
            try:
                xml = get_text(f"{self.base_url}/search?{params}", timeout=6)
                root = ET.fromstring(xml)
                if root.tag != "rss":
                    raise ET.ParseError("Expected RSS search response")
            except Exception as exc:
                if isinstance(exc, TimeoutError) or (isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError)):
                    status = "timeout"
                elif isinstance(exc, ET.ParseError):
                    status = "parse_error"
                else:
                    status = "http_error"
                diagnostic.update(status=status, error=str(exc) or type(exc).__name__)
                if not book.get("served_name"):
                    diagnostic.update(status="identity_error", failure_status=status)
                if isinstance(exc, urllib.error.HTTPError):
                    diagnostic["http_status"] = exc.code
                return results, diagnostic
            # Legacy catalogs have no content link. A successful restricted request
            # validates only the advertised name; cache it on this catalog entry.
            book["served_name"] = served_name
            diagnostic["served_name"] = served_name
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = self.local_link((item.findtext("link") or "").strip())
                desc = html_to_text(html.unescape(item.findtext("description") or ""))
                if title and link:
                    results.append({"title": title, "link": link, "snippet": desc,
                                    "book": book["title"], "book_name": book["name"]})
            diagnostic.update(status="success" if results else "zero_hits", hits=len(results))
            return results, diagnostic

        # Cover every selected library with a bounded number of concurrent requests.
        with ThreadPoolExecutor(max_workers=4) as pool:
            batches = list(pool.map(search_book, ordered))
        results = [result for batch, _ in batches for result in batch]
        if diagnostics is not None:
            diagnostics.extend(diagnostic for _, diagnostic in batches)
        terms = set(tokenize(query))
        def relevance(result):
            title = set(tokenize(result["title"]))
            snippet = set(tokenize(result["snippet"]))
            return 2 * len(terms & title) + len(terms & snippet)
        results.sort(key=relevance, reverse=True)
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
