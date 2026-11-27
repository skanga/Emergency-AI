"""Kiwix server integration (kiwix-serve or the Kiwix Desktop "Local Kiwix Server").

Use the public full-text search API: /search?pattern=...&format=xml
and download article content as context for the AI.
"""

import html
from collections import OrderedDict
import threading
import time
import os
import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .config import CONFIG_DIR, load_json
from .net import get_text, is_up, ResponseTooLarge
from .passages import extract_passages
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
        self._catalog_lock = threading.Lock()
        self._catalog_error = None
        self._catalog_failure = None
        self._cache = OrderedDict()
        self._cache_chars = 0
        self._cache_lock = threading.Lock()
        self._catalog_checked = 0

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

    def invalidate_catalog(self):
        """Invalidate catalog state under the same lock used by its readers."""
        with self._catalog_lock:
            self._books = None
            self._catalog_checked = 0
            self._catalog_error = None
            self._catalog_failure = None

    def books(self, deadline=None, diagnostics=None):
        """Return a caller-owned catalog snapshot with matching diagnostics.

        Serialize refreshes so one slow fetch cannot overwrite a newer result.
        A retrieval deadline also bounds time spent waiting for another refresh.
        """
        timeout = -1 if deadline is None else max(0, deadline - time.monotonic())
        if not self._catalog_lock.acquire(timeout=timeout):
            if diagnostics is not None:
                diagnostics.append(dict(status='catalog_error', failure_status='timeout',
                                        error='Catalog refresh wait exceeded deadline'))
            return []
        try:
            return [dict(book) for book in self._load_books(deadline, diagnostics)]
        finally:
            self._catalog_lock.release()

    def _load_books(self, deadline=None, diagnostics=None):
        """Read or refresh catalog state while the caller holds _catalog_lock."""
        if self._books is not None:
            return self._books
        books = []
        try:
            xml = get_text(self.base_url + "/catalog/v2/entries?count=-1", timeout=5, deadline=deadline, allowed_origin=self.base_url)
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
                    archive_uuid = re.sub(r"^urn:uuid:", "", entry.findtext("a:id", default="", namespaces=ns))
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
            self._catalog_failure = failure_status(exc)
            self._catalog_error = str(exc) or type(exc).__name__
            if diagnostics is not None:
                diagnostics.append(dict(status='catalog_error', failure_status=failure_status(exc),
                                        error=str(exc) or type(exc).__name__))
            return []
        self._catalog_error = None
        self._catalog_failure = None
        self._books = books
        self._catalog_checked = time.monotonic()
        return books

    def search(self, query, lang="en", limit=3, book_names=None, diagnostics=None):
        """Search logical selections (None = all editions, [] = none).

        Optional diagnostics is a caller-owned list of per-library outcomes;
        failures remain distinguishable from a successful search with zero hits.
        """
        if book_names == []:
            return []
        books = self.books(diagnostics=diagnostics)
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
        from .retrieval import run_jobs
        deadline = time.monotonic() + 8
        results = []
        jobs = [(book, query) for book in ordered[:20]]
        for (book, _), outcome, error in run_jobs(jobs, lambda job: self.search_book(*job, deadline=deadline), deadline):
            if error:
                outcome = ([], dict(name=book['name'], status=failure_status(error), error=str(error)))
            batch, diagnostic = outcome
            results.extend(batch)
            if diagnostics is not None:
                diagnostics.append(diagnostic)
        if diagnostics is not None:
            diagnostics.extend(dict(name=b['name'], status='not_searched_budget') for b in ordered[20:])
        terms = set(tokenize(query))
        def relevance(result):
            title = set(tokenize(result["title"]))
            snippet = set(tokenize(result["snippet"]))
            return 2 * len(terms & title) + len(terms & snippet)
        results.sort(key=relevance, reverse=True)
        return results[:limit]

    def search_book(self, book, query, deadline=None):
        """One restricted search; return hits and its explicit diagnostic."""
        served_name = book.get('served_name') or book['name']
        diagnostic = dict(name=book['name'], served_name=book.get('served_name'),
                          archive_uuid=book.get('archive_uuid', ''), query=query, hits=0)
        if book.get('identity_error'):
            return [], dict(diagnostic, status='identity_error', error='Invalid catalog content link')
        params = urllib.parse.urlencode({'pattern': query, 'books.name': served_name,
                                         'format': 'xml', 'pageLength': 8})
        try:
            raw = get_text(f'{self.base_url}/search?{params}', timeout=6, deadline=deadline, allowed_origin=self.base_url)
            root = ET.fromstring(raw)
            if root.tag != 'rss':
                raise ET.ParseError('Expected RSS search response')
            results = []
            for rank, item in enumerate(root.iter('item'), 1):
                if rank > 8:
                    break
                title = (item.findtext('title') or '').strip()
                link = self.local_link((item.findtext('link') or '').strip())
                if title and link:
                    results.append(dict(title=title, link=link,
                                        snippet=html_to_text(html.unescape(item.findtext('description') or '')),
                                        book=book['title'], book_name=book['name'],
                                        archive_uuid=book.get('archive_uuid', ''), issued=book.get('issued', ''),
                                        served_name=served_name, native_rank=rank, queries=[query]))
            book['served_name'] = served_name
            self._remember_served_name(book, served_name, deadline)
            return results, dict(diagnostic, served_name=served_name,
                                 status='success' if results else 'zero_hits', hits=len(results))
        except Exception as exc:
            status = failure_status(exc)
            diagnostic.update(status=status, error=str(exc) or type(exc).__name__)
            if not book.get('served_name'):
                diagnostic.update(status='identity_error', failure_status=status)
            if isinstance(exc, urllib.error.HTTPError):
                diagnostic['http_status'] = exc.code
            return [], diagnostic

    def _remember_served_name(self, book, served_name, deadline):
        """Publish legacy identity discovery only to the same catalog edition."""
        timeout = -1 if deadline is None else max(0, deadline - time.monotonic())
        if not self._catalog_lock.acquire(timeout=timeout):
            return  # Cache population must not extend the retrieval deadline.
        try:
            identity = ('name', 'archive_uuid', 'issued', 'content_url', 'identity_error')
            for current in self._books or []:
                if not current.get('served_name') and all(current.get(key) == book.get(key) for key in identity):
                    current['served_name'] = served_name
        finally:
            self._catalog_lock.release()

    def article_html(self, link, timeout=8, max_bytes=8 * 1024 * 1024, deadline=None):
        link = self.local_link(link)
        if not link:
            raise ValueError('Article link is outside the configured Kiwix service')
        return get_text(urllib.parse.urljoin(self.base_url + '/', link), timeout=timeout,
                        max_bytes=max_bytes, deadline=deadline, allowed_origin=self.base_url)

    def article_passages(self, hit, deadline=None):
        """Versioned, byte-bounded memory cache; complete source sections only."""
        version = hit.get('archive_uuid') or hit.get('served_name') or hit['book_name']
        version += ':' + hit.get('issued', '')
        key = (version, hit['link'], 'passages-v1')
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
        raw = self.article_html(hit['link'], deadline=deadline)
        passages = extract_passages(raw, archive=hit['book_name'], version=version, article_url=hit['link'])
        size = sum(len(p.text) + sum(map(len, p.heading_path)) for p in passages)
        with self._cache_lock:
            # Evict old versions of the same article, as well as LRU entries.
            for old in list(self._cache):
                if old[1] == key[1] and old != key:
                    self._cache_chars -= sum(len(p.text) + sum(map(len, p.heading_path)) for p in self._cache.pop(old))
            if size <= 4 * 1024 * 1024 and key not in self._cache:
                self._cache[key] = passages
                self._cache_chars += size
                while self._cache_chars > 4 * 1024 * 1024 or len(self._cache) > 64:
                    _, removed = self._cache.popitem(last=False)
                    self._cache_chars -= sum(len(p.text) + sum(map(len, p.heading_path)) for p in removed)
        return passages

    def article_text(self, link, max_chars=20000):
        # Compatibility API. Retrieval uses structural article_passages instead.
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 0:
            raise ValueError("max_chars must be a nonnegative integer")
        if max_chars == 0 or not self.local_link(link):
            return ""
        return html_to_text(self.article_html(link))[:max_chars]


def failure_status(exc):
    if isinstance(exc, TimeoutError) or (isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError)):
        return 'timeout'
    if isinstance(exc, ResponseTooLarge):
        return 'oversize'
    if isinstance(exc, (ET.ParseError, UnicodeError)):
        return 'parse_error'
    if isinstance(exc, urllib.error.HTTPError):
        return 'http_error'
    return 'error'
