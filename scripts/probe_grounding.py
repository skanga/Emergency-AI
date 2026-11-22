#!/usr/bin/env python3
"""Probe grounding against a running Emergency AI server (standard library only).

Run: python3 scripts/probe_grounding.py --url http://localhost:8090
Expectations are advisory, not assertions of source relevance. Inspect the JSON
report to judge whether passages actually support the generated claims.
"""
import json
import time
import argparse
from pathlib import Path
from urllib.request import Request, urlopen


CASES = [
    ('grounded', 'How do I purify drinking water?'),
    ('ungrounded', 'Write Python code to simulate water flowing through a pipe.'),
    ('grounded', 'How do I sharpen a knife?'),
    ('ungrounded', 'Write a Python script to calculate a 15-degree angle.'),
    ('grounded', 'How do I keep a computer running during a power outage?'),
    ('ungrounded', 'How do I compute the first 15 prime numbers?'),
    ('grounded', 'Which knots help secure a shelter?'),
    ('ungrounded', 'Explain knot theory in mathematics.'),
    ('grounded', 'How should I store emergency food?'),
    ('ungrounded', 'How should I store Python objects in a database?'),
    ('review', 'Write a Python checklist app for emergency supplies.'),
    ('review', 'Explain how batteries work, then estimate my laptop’s runtime.'),
    ('review', 'How do I back up my files without internet?'),
    ('review', 'What is the rule of three in mathematics?'),
    ('ungrounded', 'write a python script to compute the 1st 15 fibonacci numbers'),
]


def read_answer(stream):
    """Collect the server's SSE response; never treat a partial stream as success."""
    result = {'sources': [], 'answer': '', 'info': None}
    event, data = '', []
    for raw in stream:
        line = raw.decode('utf-8').rstrip('\r\n')
        if line.startswith('event:'):
            event = line[6:].strip()
        elif line.startswith('data:'):
            data.append(line[5:].lstrip())
        elif not line:
            if data:
                value = json.loads('\n'.join(data))
                if event == 'error':
                    raise RuntimeError(value.get('error', str(value)))
                if event == 'sources':
                    result['sources'] = value
                elif event == 'token':
                    result['answer'] += value
                elif event == 'done':
                    result['info'] = value
                    return result
            event, data = '', []
    raise RuntimeError('Stream ended without a completion event')


def ask(url, question, timeout, use_kiwix):
    payload = json.dumps({'q': question, 'lang': 'en', 'history': [],
                          'use_llm': True, 'use_kiwix': use_kiwix}).encode('utf-8')
    request = Request(url.rstrip('/') + '/api/ask', data=payload,
                      headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
    with urlopen(request, timeout=timeout) as response:
        return read_answer(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8090')
    parser.add_argument('--timeout', type=float, default=600,
                        help='Socket read timeout in seconds (default: 600)')
    parser.add_argument('--no-kiwix', action='store_true', help='Test only the bundled/local guides')
    parser.add_argument('--output', type=Path, default=Path('grounding-report.json'))
    parser.add_argument('--question', help='Test one custom question instead of the built-in set')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    cases = [('review', args.question)] if args.question else CASES
    report = {'url': args.url, 'use_kiwix': not args.no_kiwix, 'results': []}
    errors = 0
    print('Expectations describe likely support, not retrieval. Source availability does not prove relevance.')
    for index, (expected, question) in enumerate(cases, 1):
        print(f'\n[{index}/{len(cases)}] {question}', flush=True)
        started = time.monotonic()
        row = {'question': question, 'expected': expected}
        try:
            row.update(ask(args.url, question, args.timeout, not args.no_kiwix))
            info = row['info']
            if info.get('mode') == 'llm':
                actual = {True: 'sources_supplied', False: 'no_sources_supplied'}.get(info.get('sources_supplied'), 'unknown')
            else:
                actual = 'search'
            row['actual'] = actual
            warnings = []
            if expected == 'ungrounded' and actual == 'sources_supplied':
                warnings.append('review relevance and labeling of unsourced portions')
            if expected == 'grounded' and actual != 'sources_supplied':
                warnings.append('expected supporting passages; inspect retrieval')
            if actual == 'unknown':
                warnings.append('server lacks sources_supplied metadata; update server')
            if info.get('sources_supplied') is False and info.get('mode') == 'llm':
                if 'Not backed by local sources' not in row['answer']:
                    warnings.append('missing ungrounded-answer label')
            if info.get('generation', {}).get('incomplete'):
                warnings.append('generation incomplete')
            if info.get('reason'):
                warnings.append(info['reason'])
            row['warnings'] = warnings
            print(f'  {actual}; sources={len(row["sources"])}; model={info.get("llm")}')
            for source in row['sources']:
                print(f'  [{source.get("n")}] {source.get("doc_title")} / {source.get("section")}')
            for warning in warnings:
                print('  REVIEW:', warning)
            print('  Preview:', row['answer'][:240].replace('\n', ' '))
        except (OSError, ValueError, RuntimeError) as exc:
            errors += 1
            row['error'] = str(exc)
            print('  ERROR:', exc)
        row['elapsed_seconds'] = round(time.monotonic() - started, 2)
        report['results'].append(row)
        # Save after each request so an interrupted run retains completed cases.
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nReport: {args.output.resolve()} ({errors} request errors)')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
