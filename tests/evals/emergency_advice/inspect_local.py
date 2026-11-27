"""Run selected quality cases against this checkout and inspect withheld drafts.

Evaluation only: starts a temporary loopback server, uses an already-running
model/Kiwix, and records drafts explicitly. Never use this as the app launcher.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from app.answer_validation import validate_answer
from app.engine import Engine
from app.server import BoundedHTTPServer, make_handler
from tests.evals.emergency_advice import runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--manifest', default=str(Path(__file__).with_name('cases.json')))
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--trials', type=int, default=2)
    parser.add_argument('--llm-url', default='http://127.0.0.1:8091/v1')
    parser.add_argument('--kiwix-url', default='http://127.0.0.1:8092')
    parser.add_argument('--document-index-dir')
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    settings = dict(llm_backend='llamacpp', llm_url=args.llm_url,
                    kiwix_url=args.kiwix_url, kiwix_enabled=True)
    if args.document_index_dir:
        settings['document_index_dir'] = args.document_index_dir
    engine = Engine(settings)
    model = engine.llm(force=True)
    if model is None:
        raise SystemExit('Model unavailable; no generation evaluation performed')
    files = list((ROOT/'app').rglob('*.py')) + list((ROOT/'app/data').glob('*.json')) + list((ROOT/'config').glob('*.json'))
    provenance = dict(created_at=datetime.now(timezone.utc).isoformat(), settings=settings,
                      model=model.describe(), options=model.options(),
                      files_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    captures, inspections = [], []
    def inspect(answer, sources, question, lang='en', history=None):
        rendered, report = validate_answer(answer, sources, question, lang, history)
        captures.append(dict(draft=answer, sources=sources, validation=report))
        return rendered, report
    original_ask = runner.ask
    def ask(*positional, **kwargs):
        captures.clear()
        result = original_ask(*positional, **kwargs)
        trial = 1 + sum(row['id'] == result['id'] for row in inspections)
        inspections.append(dict(id=result['id'], trial=trial, validation_inputs=list(captures)))
        (out/'inspection.json').write_text(json.dumps(inspections,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result
    server = BoundedHTTPServer(('127.0.0.1',0), make_handler(engine,settings))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with patch('app.engine.validate_answer',side_effect=inspect), patch.object(runner,'ask',side_effect=ask):
            runner.run(SimpleNamespace(url=f'http://127.0.0.1:{server.server_port}',
                       output=str(out/'run'), group='all', case=args.case,
                       trials=args.trials, timeout=240, root=None), runner.read(args.manifest))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
