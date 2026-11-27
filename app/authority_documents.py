"""Explicit downloads for offline reading; raw manuals never enter answer retrieval."""
import argparse
import json
from pathlib import Path

from .config import ROOT
from .downloads import download

CATALOG = Path(__file__).resolve().parent.parent / 'config/authority-documents.json'


def prepare_documents(root, ids):
    """Validate the whole selection before downloading any pinned original."""
    documents = json.loads(CATALOG.read_text(encoding='utf-8'))['documents']
    by_id = {d['id']: d for d in documents}
    selected = []
    for identity in dict.fromkeys(ids):
        if identity not in by_id:
            raise ValueError(f'Unknown authority document: {identity}')
        document = by_id[identity]
        if not document['download']:
            raise ValueError(f'{identity}: no verified binary download; see {document["source_url"]}')
        selected.append(document)
    folder = Path(root) / 'runtime' / 'authorities'
    folder.mkdir(parents=True, exist_ok=True)
    # Write notices for the complete catalog so later selections retain earlier rights.
    notice = '# Optional original authority documents\n\n'
    notice += ('For offline reading. These files are not automatically searched by the assistant. '
               'The application MIT license does not relicense third-party documents. '
               'Downloading does not grant redistribution rights.\n\n')
    for document in documents:
        notice += f'## {document["title"]}\n\n{document["rights"]}\n\nSource: {document["source_url"]}\n\n'
    (folder / 'README.md').write_text(notice, encoding='utf-8')
    result = []
    for document in selected:
        artifact = document['download']
        path = folder / artifact['filename']
        download(artifact['url'], str(path), expected_size=artifact['bytes'], sha256=artifact['sha256'])
        result.append(str(path))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(ROOT))
    parser.add_argument('--document', action='append', required=True,
                        help='Repeat for ifrc-2025, who-cfar or fema-ready. Publisher terms apply.')
    args = parser.parse_args()
    try:
        for path in prepare_documents(args.root, args.document):
            print(path)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f'Authority download stopped: {exc}\n')


if __name__ == '__main__':
    main()
