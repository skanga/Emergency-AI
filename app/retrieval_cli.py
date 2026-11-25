"""Explicit retrieval inspection and offline document preparation commands."""

import json
from pathlib import Path
import sys
from urllib.parse import urljoin

from .document_index import DocumentIndex, prepare_collection
from .document_tools import prepare_tool, tool_status
from .engine import Engine
from .kiwix import KiwixClient
from .net import get_bytes

ROOT = Path(__file__).resolve().parent.parent


def summary_text(report, sources, lang='en'):
    labels = {
        'en': ('Library passages used', 'searched', 'no matches', 'search failed', 'not searched: limit'),
        'pt': ('Trechos de bibliotecas usados', 'pesquisada', 'sem resultados', 'falha na busca', 'não pesquisada: limite'),
        'es': ('Pasajes de bibliotecas usados', 'buscada', 'sin resultados', 'falló la búsqueda', 'sin buscar: límite'),
    }[lang]
    count = sum(s.get('kind') == 'kiwix' and not s.get('context_omitted') for s in sources)
    lines = [labels[0] + ': ' + str(count)]
    if report.get('status') and report['status'] != 'success':
        status = report['status']
        if status == 'zero_hits' and any(row.get('hits', 0) for row in report.get('libraries', [])):
            status = 'no_relevant_passage'
        lines.append(state_label(status, lang))
    failures = sum(row.get('status') not in ('success','rejected','empty_content','not_fetched_budget') for row in report.get('fetches', []))
    if failures:
        lines.append({'en':'Article fetch failures', 'pt':'Falhas ao buscar artigos', 'es':'Fallos al obtener artículos'}[lang] + ': ' + str(failures))
    if report.get('not_fetched_budget'):
        lines.append(labels[4] + ': ' + str(report['not_fetched_budget']))
    for library in report.get('libraries', []):
        state = library.get('status')
        label = labels[1] if state == 'success' else labels[2] if state == 'zero_hits' else labels[4] if state == 'not_searched_budget' else labels[3]
        line = library['name'] + ': ' + label
        index_state = library.get('index', {}).get('state')
        if index_state and index_state != 'not_applicable':
            line += ' · ' + state_label(index_state, lang)
        lines.append(line)
    return '\n'.join(lines)


def state_label(state, lang='en'):
    keys = ['disabled','no_selection','catalog_error','failed','partial','zero_hits','no_relevant_passage','index_needed','indexed','partially_indexed','browse_only','context_budget','token_budget','conflict_unresolved','reviewed_precedence']
    text = {
        'en':['disabled','none selected','catalog unavailable','Retrieval failed','Retrieval partially completed','no matches','no relevant passage','PDF index needed','indexed','partially indexed','browse only','Context limit','Model context limit','Unresolved disagreement','Superseded by reviewed policy'],
        'pt':['desativada','nenhuma selecionada','catálogo indisponível','Falha na recuperação','Recuperação parcial','sem resultados','sem trecho relevante','PDF precisa de índice','indexada','parcialmente indexada','somente leitura','Limite de contexto','Limite do modelo','Divergência não resolvida','Substituído por revisão'],
        'es':['desactivada','ninguna seleccionada','catálogo no disponible','Falló la recuperación','Recuperación parcial','sin resultados','sin pasaje relevante','PDF necesita índice','indexada','parcialmente indexada','solo lectura','Límite de contexto','Límite del modelo','Desacuerdo no resuelto','Sustituido por revisión'],
    }[lang]
    return dict(zip(keys,text)).get(state, {'en':'Unavailable','pt':'Indisponível','es':'No disponible'}[lang])


def conflict_notice(report, lang='en'):
    parts = []
    for conflict in report.get('conflicts', []):
        if conflict['resolution'] == 'unresolved':
            parts.append({'en':'Sources disagree; contested advice withheld.', 'pt':'As fontes divergem; orientação contestada omitida.', 'es':'Las fuentes discrepan; consejo en disputa omitido.'}[lang])
        else:
            parts.append({'en':'Reviewed source correction: ', 'pt':'Correção de fonte revisada: ', 'es':'Corrección de fuente revisada: '}[lang] + conflict.get('explanation', ''))
    return '\n'.join(parts)


def _selection(value):
    return None if value is None else [part.strip() for part in value.split(',') if part.strip()]


def diagnose(args, settings):
    engine = Engine(settings)
    question = ' '.join(args.text)
    report = {}
    sources = engine.retrieve(question, args.lang, kiwix_books=_selection(args.libraries), diagnostics=report)
    result = {'question': question, 'language': args.lang, 'retrieval': report, 'sources': sources}
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0


def index_libraries(args, settings):
    tools_root = ROOT / 'runtime/document-tools'
    tool = prepare_tool(tools_root) if args.prepare_tool else tool_status(tools_root)
    if tool['state'] != 'available':
        print(json.dumps(tool))
        return 2
    client = KiwixClient(settings.get('kiwix_url', 'http://127.0.0.1:8092'))
    books = client.books()
    selected = _selection(args.libraries)
    if selected is not None:
        missing = set(selected) - {book['name'] for book in books}
        if missing:
            print(json.dumps({'state':'selection_missing', 'libraries': sorted(missing)}))
            return 2
        books = [book for book in books if book['name'] in selected]
    index = DocumentIndex(settings.get('document_index_dir', ROOT / 'indexes'))

    def fetch(link, **limits):
        local = client.local_link(link)
        if not local:
            raise ValueError('foreign_document_url')
        return get_bytes(urljoin(client.base_url + '/', local),
                         allowed_origin=client.base_url, **limits)

    reports = []
    try:
        for book in books:
            try:
                state = prepare_collection(book, index, tool['path'], fetch,
                                           progress=lambda event: print(json.dumps(event), file=sys.stderr))
            except (OSError, ValueError, RuntimeError) as exc:
                state = {'state':'preparation_failed', 'reason':type(exc).__name__, 'detail':str(exc)[:160]}
            reports.append(dict(state, name=book['name'], archive_uuid=book.get('archive_uuid')))
        if args.cleanup:
            reports.append({'removed_indexes': index.cleanup(books)})
    except KeyboardInterrupt:
        print(json.dumps({'state':'cancelled', 'completed':reports, 'last_complete_indexes_retained':True}))
        return 130
    print(json.dumps({'libraries':reports}, ensure_ascii=False, indent=2))
    return 2 if any(r.get('state') in ('preparation_failed', 'refresh_failed') for r in reports) else 0
