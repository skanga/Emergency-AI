"""Prepared document evidence. Serving never invokes an extractor or downloads tools."""

import ast
from contextlib import closing
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import quote, unquote, urlsplit

INDEX_VERSION = 1

ZIM_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config/zims.json'


@lru_cache(maxsize=1)
def _fts5_supported():
    """SQLite capabilities are fixed for this process, unlike index contents."""
    try:
        with closing(sqlite3.connect(':memory:')) as db:
            db.execute('CREATE VIRTUAL TABLE probe USING fts5(text)')
        return True
    except sqlite3.OperationalError:
        return False


@lru_cache(maxsize=8)
def _document_collections(path, mtime_ns, size, inode):
    """Cache immutable derived data; replacement and edits get a fresh key."""
    configured = json.loads(Path(path).read_text(encoding='utf-8')).get('zims', [])
    return frozenset(entry['name'] for entry in configured if entry.get('document_format') == 'nautilus')


class _RetainPreviousIndex(RuntimeError):
    """A rebuild failed; the active version must remain available."""


def document_state(book, index):
    """Known document formats need preparation; native archives do not."""
    path = ZIM_CONFIG_PATH.resolve()
    metadata = path.stat()
    collections = _document_collections(str(path), metadata.st_mtime_ns, metadata.st_size, metadata.st_ino)
    state = index.status(book)
    if book['name'] in collections or state['state'] in ('indexed', 'partially_indexed', 'browse_only'):
        return state
    return {'state': 'not_applicable'}


def parse_manifest(script, content_root):
    """Accept only the known DATABASE assignment containing literal data."""
    if len(script) > 1024 * 1024:
        raise ValueError('manifest_size_limit')
    match = re.fullmatch(r'\s*var\s+DATABASE\s*=\s*(\[.*\])\s*;?\s*', script, re.S)
    if not match:
        raise ValueError('unsupported_manifest')
    try:
        tree = ast.parse(match[1], mode='eval')
        allowed = (ast.Expression, ast.List, ast.Dict, ast.Constant, ast.Load)
        if any(not isinstance(node, allowed) for node in ast.walk(tree)):
            raise ValueError('unsupported_manifest_expression')
        entries = ast.literal_eval(tree)
    except (SyntaxError, RecursionError, TypeError) as exc:
        raise ValueError('invalid_manifest') from exc
    if not isinstance(entries, list) or len(entries) > 5000:
        raise ValueError('manifest_document_limit')
    root = content_root.rstrip('/') + '/'
    documents = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('fp'), list):
            raise ValueError('invalid_document_entry')
        for path in entry['fp']:
            if not isinstance(path, str):
                raise ValueError('invalid_document_path')
            decoded = unquote(path)
            url = urlsplit(decoded)
            if (url.scheme or url.netloc or url.query or url.fragment or decoded.startswith('/')
                    or any(part in ('', '.', '..') for part in decoded.split('/'))
                    or any(c in decoded for c in '\\%\x00\r\n') or not decoded.lower().endswith('.pdf')):
                raise ValueError('document_path_outside_archive')
            documents.append({'title': str(entry.get('ti') or decoded),
                              'author': str(entry.get('aut') or ''),
                              'link': root + quote(decoded, safe='/')})
    return documents


def usable_page(text):
    """Conservatively exclude scans, extraction corruption and column layouts.

    This is a coverage filter, not a proof that the remaining text is correct.
    """
    letters = sum(c.isalpha() for c in text)
    if letters < 30 or text.count('\ufffd') > max(2, len(text) // 100):
        return False
    if any(re.search(r'\S {3,}\S', line) for line in text.splitlines()):
        return False
    return letters / max(1, len(text)) > .45


def run_bounded(command, *, timeout=120, max_bytes=64 * 1024 * 1024, cancelled=lambda: False):
    """Run a preparation tool with bounded captured output and guaranteed cleanup."""
    if cancelled():
        raise InterruptedError('preparation_cancelled')
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=output, stderr=errors, stdin=subprocess.DEVNULL)
        try:
            while process.poll() is None:
                if cancelled():
                    raise InterruptedError('preparation_cancelled')
                if time.monotonic() >= deadline:
                    raise TimeoutError('extractor_timeout')
                if os.fstat(output.fileno()).st_size > max_bytes or os.fstat(errors.fileno()).st_size > 1024 * 1024:
                    raise ValueError('extractor_output_limit')
                time.sleep(.02)
            if process.returncode:
                raise RuntimeError('extractor_failed')
            if cancelled():
                raise InterruptedError('preparation_cancelled')
            if os.fstat(output.fileno()).st_size > max_bytes or os.fstat(errors.fileno()).st_size > 1024 * 1024:
                raise ValueError('extractor_output_limit')
            output.seek(0)
            return output.read(max_bytes + 1)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def extract_pdf(path, document, extractor, *, max_bytes=256 * 1024 * 1024,
                max_pages=2000, timeout=120, cancelled=lambda: False):
    """Extract pages only during preparation; reject suspect layouts as coverage gaps."""
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError('pdf_size_limit')
    with path.open('rb') as stream:
        if not stream.read(8).startswith(b'%PDF-'):
            raise ValueError('unsupported_document_format')
    deadline = time.monotonic() + timeout
    suffix = '.exe' if str(extractor).endswith('.exe') else ''
    info_tool = str(Path(extractor).with_name('pdfinfo' + suffix))
    info = run_bounded([info_tool, str(path)], timeout=min(timeout, 10), max_bytes=1024 * 1024, cancelled=cancelled)
    match = re.search(rb'^Pages:\s*(\d+)', info, re.M)
    if not match or not 0 < int(match[1]) <= max_pages:
        raise ValueError('pdf_page_limit_or_unknown')
    count = int(match[1])
    raw = run_bounded([str(extractor), '-layout', '-enc', 'UTF-8', str(path), '-'],
                      timeout=max(.001, deadline - time.monotonic()), cancelled=cancelled)
    pages = raw.decode('utf-8', errors='replace').split('\f')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            if cancelled():
                raise InterruptedError('preparation_cancelled')
            if time.monotonic() >= deadline:
                raise TimeoutError('extractor_timeout')
            digest.update(chunk)
    rows, excluded = [], []
    for number in range(1, count + 1):
        if cancelled():
            raise InterruptedError('preparation_cancelled')
        if time.monotonic() >= deadline:
            raise TimeoutError('extractor_timeout')
        text = pages[number - 1].strip() if number <= len(pages) else ''
        if not usable_page(text):
            excluded.append(number)
            continue
        rows.append({'text': text, 'title': document['title'], 'page': number,
                     'link': document['link'] + '#page=' + str(number),
                     'document_hash': digest.hexdigest(), 'author': document.get('author', '')})
    if time.monotonic() >= deadline:
        raise TimeoutError('extractor_timeout')
    return rows, {'pages': count, 'excluded_pages': excluded}


def prepare_collection(book, index, extractor, fetch, *, progress=lambda event: None,
                       cancelled=lambda: False, max_bytes=256 * 1024 * 1024,
                       max_pages=2000, timeout=120):
    """Prepare a known Nautilus collection with an injected same-service transport.

    fetch(link, max_bytes=..., timeout=...) must enforce streaming body limits.
    No JavaScript executes, and no preparation happens inside search().
    """
    if cancelled():
        raise InterruptedError('preparation_cancelled')
    index.identity(book)
    root = book.get('content_url')
    if not root or book.get('identity_error'):
        raise ValueError('identity_invalid')
    root = root.rstrip('/')
    script = fetch(root + '/database.js', max_bytes=1024 * 1024, timeout=min(timeout, 15))
    documents = parse_manifest(script.decode('utf-8'), root + '/files/')
    coverage = {'documents': len(documents), 'pages': 0, 'excluded_pages': [], 'failures': [], 'document_reports': {}}
    previous = index.status(book)
    keep_previous = previous['state'] in ('indexed', 'partially_indexed', 'browse_only')

    def passages():
        for document in documents:
            if cancelled():
                raise InterruptedError('preparation_cancelled')
            progress({'stage': 'document', 'title': document['title'], 'link': document['link']})
            try:
                deadline = time.monotonic() + timeout
                data = fetch(document['link'], max_bytes=max_bytes, timeout=min(timeout, 60))
                if len(data) > max_bytes:
                    raise ValueError('pdf_size_limit')
                digest = hashlib.sha256(data).hexdigest()
                cached = index.cached_document(book, document['link'], digest)
                if cached:
                    rows, report = cached
                else:
                    with tempfile.TemporaryDirectory() as temporary:
                        pdf = Path(temporary) / 'document.pdf'
                        pdf.write_bytes(data)
                        rows, report = extract_pdf(pdf, document, extractor, max_bytes=max_bytes,
                                                   max_pages=max_pages, timeout=max(.001, deadline - time.monotonic()), cancelled=cancelled)
                del data
                if time.monotonic() >= deadline:
                    raise TimeoutError('document_preparation_timeout')
                for row in rows:
                    row['document_hash'] = digest
                    row.update(title=document['title'], author=document.get('author', ''))
                coverage['document_reports'][document['link']] = dict(report, document_hash=digest)
                coverage['pages'] += report['pages']
                coverage['excluded_pages'].extend({'link': document['link'], 'page': page,
                                                   'reason': 'unreadable_or_suspect_layout'}
                                                  for page in report['excluded_pages'])
                for row in rows:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('document_preparation_timeout')
                    yield row
            except InterruptedError:
                raise
            except (OSError, ValueError, RuntimeError) as exc:
                coverage['failures'].append({'link': document['link'], 'reason': type(exc).__name__,
                                            'detail': str(exc)[:160]})
        if keep_previous and coverage['failures']:
            raise _RetainPreviousIndex('document_refresh_failed')
    try:
        index.replace(book, passages(), coverage, cancelled=cancelled)
    except _RetainPreviousIndex:
        return dict(previous, state='refresh_failed', previous_state=previous['state'],
                    retained_previous_index=True, refresh_failures=coverage['failures'])
    return index.status(book)


class DocumentIndex:
    def __init__(self, root):
        self.root = Path(root).resolve()

    @staticmethod
    def identity(book):
        if not book.get('archive_uuid') or not book.get('served_name'):
            raise ValueError('index_requires_versioned_archive_identity')
        return '\0'.join((str(INDEX_VERSION), book['archive_uuid'], book['served_name']))

    def _path(self, book):
        key = hashlib.sha256(self.identity(book).encode()).hexdigest()
        return self.root / (key + '.sqlite3')

    @staticmethod
    def supported():
        return _fts5_supported()

    def status(self, book):
        if not self.supported():
            return {'state': 'unsupported_index', 'reason': 'sqlite_fts5_missing'}
        try:
            path = self._path(book)
        except ValueError:
            return {'state': 'identity_invalid'}
        if not path.is_file():
            return {'state': 'index_needed'}
        try:
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                coverage = json.loads(db.execute('SELECT value FROM metadata WHERE key=?', ('coverage',)).fetchone()[0])
                if not isinstance(coverage, dict):
                    raise ValueError('invalid_index_metadata')
                if not isinstance(coverage.get('document_reports', {}), dict) or not isinstance(coverage.get('excluded_pages', []), list):
                    raise ValueError('invalid_index_metadata')
                count = db.execute('SELECT count(*) FROM passages').fetchone()[0]
            return dict(coverage, state=('partially_indexed' if coverage.get('excluded_pages') or coverage.get('failures') else 'indexed') if count else 'browse_only', passages=count)
        except (sqlite3.Error, ValueError, TypeError):
            return {'state': 'index_needed', 'reason': 'index_invalid'}

    def cached_document(self, book, link, digest):
        report = self.status(book).get('document_reports', {}).get(link)
        if not isinstance(report, dict) or report.get('document_hash') != digest:
            return None
        try:
            with closing(sqlite3.connect(self._path(book).as_uri() + '?mode=ro', uri=True)) as db:
                rows = [json.loads(raw) for (raw,) in db.execute('SELECT source FROM passages WHERE source LIKE ?', ('%' + digest + '%',))]
            rows = [row for row in rows if isinstance(row, dict) and row.get('document_hash') == digest
                    and row.get('link', '').split('#')[0] == link]
            if len(rows) + len(report.get('excluded_pages', [])) != report.get('pages'):
                return None
            return rows, report
        except (sqlite3.Error, ValueError, TypeError):
            return None

    def cleanup(self, current_books):
        """Explicitly reclaim only recognized generated indexes of old versions."""
        keep = {self._path(book) for book in current_books if book.get('archive_uuid') and book.get('served_name')}
        removed = 0
        for path in self.root.glob('*.sqlite3'):
            if path in keep or not re.fullmatch(r'[0-9a-f]{64}\.sqlite3', path.name):
                continue
            try:
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                    marker = db.execute('SELECT value FROM metadata WHERE key=?', ('format',)).fetchone()
                if marker != ('emergency-document-index',):
                    continue
                path.unlink()
                removed += 1
            except sqlite3.Error:
                continue
        return removed

    def replace(self, book, passages, coverage, *, cancelled=lambda: False):
        """Atomic activation: cancellation/errors retain the previous index."""
        if not self.supported():
            raise RuntimeError('sqlite_fts5_missing')
        destination = self._path(book)
        self.root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(suffix='.tmp', dir=self.root)
        os.close(fd)
        try:
            with closing(sqlite3.connect(name)) as db:
                db.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT)')
                db.execute('INSERT INTO metadata VALUES(?,?)', ('format', 'emergency-document-index'))
                db.execute('CREATE VIRTUAL TABLE passages USING fts5(text, source UNINDEXED)')
                for passage in passages:
                    if cancelled():
                        raise InterruptedError('preparation_cancelled')
                    source = dict(passage, archive_uuid=book.get('archive_uuid', ''),
                                  served_name=book.get('served_name'), book_name=book['name'],
                                  language=book.get('lang', ''), issued=book.get('issued', ''),
                                  extraction_version=INDEX_VERSION)
                    source.pop('id', None)
                    source['id'] = hashlib.sha256((self.identity(book) + json.dumps(source, sort_keys=True)).encode()).hexdigest()[:24]
                    db.execute('INSERT INTO passages(text,source) VALUES(?,?)', (source['text'], json.dumps(source)))
                db.execute('INSERT INTO metadata VALUES(?,?)', ('coverage', json.dumps(coverage)))
                db.commit()
            if cancelled():
                raise InterruptedError('preparation_cancelled')
            os.replace(name, destination)
        finally:
            Path(name).unlink(missing_ok=True)

    def search(self, queries, books, limit=12):
        """Only selected exact archive versions are eligible. No fallback to old indexes."""
        results, seen = [], set()
        for book in books:
            try:
                path = self._path(book)
            except ValueError:
                continue
            if not path.is_file():
                continue
            try:
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                    for query in queries:
                        words = re.findall(r'\w+', query)[:12]
                        if not words:
                            continue
                        expression = ' AND '.join('"' + word + '"' for word in words)
                        rows = db.execute('SELECT source FROM passages WHERE passages MATCH ? ORDER BY bm25(passages) LIMIT ?', (expression, max(0, min(limit, 40))))
                        for (raw,) in rows:
                            source = json.loads(raw)
                            if not isinstance(source, dict) or not all(isinstance(source.get(k), str) for k in ('id', 'text', 'link')):
                                continue
                            if source['id'] not in seen:
                                results.append(source)
                                seen.add(source['id'])
            except (sqlite3.Error, ValueError, KeyError):
                continue  # status() exposes invalid indexes; native/local retrieval can continue.
        return results[:limit]
