#!/usr/bin/env python3
"""Evaluate natural questions through production retrieval and prompt construction.

Gold matches measure retrieval, not clinical correctness. Precision and answer
safety require independent annotation; this tool never fabricates those labels.
"""

import argparse
import json
import math
from pathlib import Path
import sys
import time
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.config import load_settings
from app.engine import Engine
from app.llm import LLMError


def measure_gold(case, sources):
    gold = case.get('gold_passages', [])
    matched = []
    for source in sources:
        if source.get('context_omitted'):
            continue
        link = urlsplit(source.get('link', ''))
        path, anchor = unquote(link.path), unquote(link.fragment)
        for expected in gold:
            if (('/' + expected['served_name'] + '/') in path
                    and path.endswith('/' + expected['article'])
                    and (not expected.get('anchor') or anchor == expected['anchor'])):
                matched.append(source.get('id', source.get('n')))
    return {'annotated': bool(gold), 'matched': bool(matched), 'source_ids': matched}


def summarize(results):
    annotated = [r for r in results if r['gold']['annotated']]
    matched = sum(r['gold']['matched'] for r in annotated)
    times = sorted(r['seconds'] for r in results)
    by_language = {}
    for language in ('en', 'pt', 'es'):
        rows = [r for r in annotated if r['language'] == language]
        by_language[language] = {'matched':sum(r['gold']['matched'] for r in rows), 'annotated':len(rows)}
    return {'cases':len(results), 'gold_recall':{'matched':matched,'annotated':len(annotated),
            'rate':matched / len(annotated) if annotated else None}, 'by_language':by_language,
            'retrieval_p95_seconds':times[max(0, math.ceil(.95 * len(times)) - 1)] if times else None,
            'unannotated_cases':len(results)-len(annotated), 'human_precision':None,
            'answer_safety_review':'pending', 'release_gates_passed':False,
            'limitation':'Gold-section matches only. Independent relevance and safety annotation is required.'}


def evaluate_case(engine, case, generate=False):
    started = time.monotonic()
    question, language = case['q'], case.get('lang', 'en')
    history = case.get('history', [])
    diagnostics = {}
    sources = engine.retrieve(question, language, history, kiwix_books=case.get('libraries'), diagnostics=diagnostics)
    messages = engine.build_messages(question, language, sources, history)
    model_fit = False
    fitting_error = None
    # Read-only token accounting can use the already running backend. No model
    # launch or generation is needed for the default retrieval evaluation.
    conflicts = diagnostics.get('conflicts', [])
    blocked_reason = 'source_conflict' if any(c['resolution'] == 'unresolved' for c in conflicts) else None
    llm = engine.llm() if not blocked_reason else None
    if llm:
        try:
            messages, sources, _ = engine.fit_messages(llm, question, language, sources, history)
            model_fit = True
        except (LLMError, OSError) as exc:
            fitting_error = type(exc).__name__
            sources = [dict(source, context_omitted=True, context_omitted_reason='model_fit_failed') for source in sources]
            messages = []
    diagnostics['included_source_ids'] = [source.get('id') for source in sources if not source.get('context_omitted')]
    diagnostics['included'] = len(diagnostics['included_source_ids'])
    preferred = {c['preferred_source'] for c in conflicts if c['resolution'] == 'reviewed_precedence'}
    if preferred - set(diagnostics['included_source_ids']) and not blocked_reason:
        blocked_reason = 'reviewed_source_omitted'
    if blocked_reason:
        messages = []
    result = {'id':case['id'], 'split':case.get('split'), 'question':question, 'language':language,
              'seconds':round(time.monotonic()-started, 3), 'retrieval':diagnostics,
              'sources':sources, 'messages':messages, 'model_token_fit':model_fit,
              'fitting_error':fitting_error, 'blocked_reason':blocked_reason,
              'gold':measure_gold(case, [] if blocked_reason else sources),
              'human_review':{'relevance':None,'safety':None}}
    if generate:
        captured = []
        original_fit = engine.fit_messages
        def capture_fit(*args, **kwargs):
            fitted = original_fit(*args, **kwargs)
            captured.append(fitted[0])
            return fitted
        engine.fit_messages = capture_fit
        try:
            answer, sources, info = engine.answer_text(question, language, history=history, kiwix_books=case.get('libraries'))
        finally:
            engine.fit_messages = original_fit
        blocked_reason = info.get('reason') if info.get('reason') in ('source_conflict','reviewed_source_omitted') else None
        messages = [] if blocked_reason else captured[-1] if captured else engine.build_messages(question, language, sources, history)
        result.update(answer=answer, sources=sources, generation=info, retrieval=info.get('retrieval', {}),
                      blocked_reason=blocked_reason, messages=messages, model_token_fit=bool(captured),
                      gold=measure_gold(case, [] if blocked_reason else sources))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default=str(Path(__file__).with_name('retrieval_manifest.json')))
    parser.add_argument('--output', help='explicit result file; otherwise JSON goes to stdout')
    parser.add_argument('--generate', action='store_true', help='also generate answers; run only after retrieval review')
    parser.add_argument('--settings', help='optional JSON settings overrides for the isolated test')
    parser.add_argument('--limit', type=int, help='bounded smoke test; not a full release evaluation')
    args = parser.parse_args()
    settings = load_settings()
    if args.settings:
        settings.update(json.loads(Path(args.settings).read_text(encoding='utf-8')))
    cases = json.loads(Path(args.manifest).read_text(encoding='utf-8'))['cases']
    if args.limit is not None:
        cases = cases[:args.limit]
    engine = Engine(settings)
    results = []
    for case in cases:
        results.append(evaluate_case(engine, case, args.generate))
        print(case['id'] + ': completed', file=sys.stderr, flush=True)
    text = json.dumps({'summary':summarize(results),'results':results}, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
