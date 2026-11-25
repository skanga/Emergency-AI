"""Heading-scoped extraction from already-fetched HTML (no network or cache).

Procedure sections stay whole. Prose may split between blocks, with scope and
cautions repeated. Character targets are soft: no source instruction is sliced.
"""

from dataclasses import dataclass, field
import hashlib
from html.parser import HTMLParser
import re


@dataclass(frozen=True)
class Passage:
    """Stable source identity and original text, with actual HTML anchor if any."""
    id: str
    text: str
    heading_path: tuple[str, ...]
    anchor: str
    archive: str
    version: str
    article_url: str


@dataclass
class _Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node('root')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        # Paragraphs close implicitly before block elements in valid HTML.
        if tag in {'p', 'div', 'section', 'ol', 'ul', 'table', 'blockquote', 'pre', 'dl', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            for index in range(len(self.stack) - 1, 0, -1):
                if self.stack[index].tag == 'p':
                    del self.stack[index:]
                    break
        # HTML's common optional end tags; tolerate truncated documents.
        peers = {'li': {'li'}, 'p': {'p'}, 'tr': {'tr'}, 'td': {'td', 'th'}, 'th': {'td', 'th'}}
        if tag in peers:
            for index in range(len(self.stack) - 1, 0, -1):
                if self.stack[index].tag in peers[tag]:
                    del self.stack[index:]
                    break
                if self.stack[index].tag in {'ol', 'ul', 'table', 'tr'}:
                    break
        node = _Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


_SKIP = {'script', 'style', 'noscript', 'nav', 'footer', 'header', 'form'}
_BOILERPLATE = {'navbox', 'navigation', 'toc', 'mw-editsection', 'sidebar', 'catlinks', 'printfooter'}
_HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_BLOCKS = {'p', 'ol', 'ul', 'table', 'blockquote', 'pre', 'dl'}


def _skip(node):
    return node.tag in _SKIP or node.attrs.get('role') == 'navigation' or bool(
        set((node.attrs.get('class') or '').split()) & _BOILERPLATE)


def _render(node):
    if isinstance(node, str):
        return node
    if _skip(node):
        return ''
    if node.tag in {'ol', 'ul'}:
        lines = []
        number = int(node.attrs.get('start', '1')) if str(node.attrs.get('start', '1')).isdigit() else 1
        for child in node.children:
            if isinstance(child, _Node) and child.tag == 'li':
                value = str(child.attrs.get('value', ''))
                if node.tag == 'ol' and re.fullmatch(r'[+-]?\d+', value):
                    number = int(value)
                marker = f'{number}. ' if node.tag == 'ol' else '- '
                lines.append(marker + _render(child).strip())
                number += 1
        return '\n' + '\n'.join(lines) + '\n'
    if node.tag == 'tr':
        return '\n' + ' | '.join(_render(c).strip() for c in node.children if isinstance(c, _Node) and c.tag in {'td', 'th'}) + '\n'
    text = ''.join(_render(c) for c in node.children)
    return '\n' + text + '\n' if node.tag in _BLOCKS or node.tag in {'div', 'section', 'br'} else text


def _clean(text):
    return '\n'.join(line.strip() for line in re.sub(r'[^\S\n]+', ' ', text).splitlines() if line.strip())


def _anchor(node):
    if node.attrs.get('id') or node.attrs.get('name'):
        return node.attrs.get('id') or node.attrs['name']
    for child in node.children:
        if isinstance(child, _Node):
            result = _anchor(child)
            if result:
                return result
    return ''


def _blocks(node):
    """Flatten structural wrappers, retaining lists/tables as atomic blocks."""
    pending = []
    for child in node.children:
        if isinstance(child, str):
            pending.append(child)
        elif not _skip(child):
            if child.tag in _HEADINGS | _BLOCKS:
                if _clean(''.join(pending)):
                    yield ('p', _clean(''.join(pending)), '')
                pending = []
                yield (child.tag, _clean(_render(child)), _anchor(child))
            else:
                if _clean(''.join(pending)):
                    yield ('p', _clean(''.join(pending)), '')
                pending = []
                yield from _blocks(child)
    if _clean(''.join(pending)):
        yield ('p', _clean(''.join(pending)), '')


def _warning(text):
    return bool(re.search(r'\b(warning|caution|never|only|do not|must not|aviso|atenção|nunca|somente|advertencia|precaución|solo|no usar)\b', text, re.I))


def extract_passages(raw_html, *, archive='', version='', article_url='', max_prose_chars=4000):
    """Return every section; caller handles fetch size, ranking and prompt budget.

    IDs include archive/version/URL, section position and text. Missing anchors
    stay empty rather than inventing a fragment that the source does not expose.
    Parent caution blocks preserve inherited applicability constraints.
    """
    if max_prose_chars < 1:
        raise ValueError('max_prose_chars must be positive')
    parser = _Parser()
    parser.feed(raw_html)
    parser.close()
    sections = []
    headings = []
    section = {'path': (), 'anchor': '', 'blocks': [], 'ancestors': []}
    for tag, text, anchor in _blocks(parser.root):
        if tag in _HEADINGS:
            if section['blocks']:
                sections.append(section)
            level = int(tag[1])
            while headings and headings[-1][0] >= level:
                headings.pop()
            ancestors = [b for _, _, parent in headings for b in parent['blocks'] if _warning(b[1])]
            section = {'path': tuple(h[1] for h in headings) + (text,), 'anchor': anchor, 'blocks': [], 'ancestors': ancestors}
            headings.append((level, text, section))
        elif text:
            section['blocks'].append((tag, text))
    if section['blocks']:
        sections.append(section)
    passages = []
    for section_index, section in enumerate(sections):
        blocks = section['blocks']
        procedure = any(tag in {'ol', 'ul', 'table'} for tag, _ in blocks)
        cautions = [text for _, text in blocks if _warning(text)]
        # A following warning subsection belongs to its parent procedure.
        for following in sections[section_index + 1:]:
            path = following['path']
            if len(path) <= len(section['path']) or path[:len(section['path'])] != section['path']:
                break
            if any(_warning(heading) or heading.lower() in {'warnings', 'cautions'} for heading in path[len(section['path']):]):
                cautions.extend(text for _, text in following['blocks'])
        inherited = [text for _, text in section['ancestors']]
        groups = [[]]
        size = 0
        for _, text in blocks:
            if not procedure and groups[-1] and size + len(text) > max_prose_chars:
                groups.append([])
                size = 0
            groups[-1].append(text)
            size += len(text)
        for index, group in enumerate(groups):
            context = inherited + group + [c for c in cautions if c not in group]
            text = '\n\n'.join(context)
            identity = '\0'.join((archive, version, article_url, str(section_index), str(index), text))
            passages.append(Passage(hashlib.sha256(identity.encode()).hexdigest()[:24], text,
                                    section['path'], section['anchor'], archive, version, article_url))
    return passages
