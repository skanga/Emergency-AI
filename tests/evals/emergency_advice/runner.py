#!/usr/bin/env python3
"""Run, import, review and compare emergency-answer evaluations (stdlib only)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.request import ProxyHandler, Request, build_opener
from urllib.parse import urlsplit

if __package__:
    from . import suite, report
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import suite
    import report

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def cases_from(path):
    doc = read(path)
    seen = set()
    for case in doc['cases']:
        ident = case['id']
        if not re.fullmatch(r'[a-z][a-z0-9_]*', ident) or ident in seen:
            raise ValueError('Invalid or duplicate case ID: ' + ident)
        if case.get('followup_of') and case['followup_of'] not in seen:
            raise ValueError('Live follow-up must follow its parent')
        if not set(case['rubric']['references']) <= set(doc['references']):
            raise ValueError('Unknown case reference')
        seen.add(ident)
    return doc


def ask(base, payload, ident, timeout=240):
    raw = {'id': ident, 'request': payload, 'answer': '', 'events': [],
           'first_token_seconds': None}
    started = time.monotonic()
    request = Request(base.rstrip('/') + '/api/ask', data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
            for event, data in suite.sse(response):
                elapsed = time.monotonic() - started
                raw['events'].append({'event': event, 'data': data, 'seconds': round(elapsed, 3)})
                if event == 'token':
                    if not isinstance(data, str):
                        raise ValueError('Token must be text')
                    if raw['first_token_seconds'] is None:
                        raw['first_token_seconds'] = elapsed
                    raw['answer'] += data
                if elapsed > timeout:
                    raise TimeoutError('Evaluation time limit exceeded')
    except (OSError, ValueError) as exc:
        raw['error'] = type(exc).__name__ + ': ' + str(exc)
    raw['total_seconds'] = time.monotonic() - started
    return raw


def payload_for(case, previous):
    # Clone so a live follow-up cannot mutate the versioned frozen request.
    payload = json.loads(json.dumps(case['request']))
    if case.get('followup_of'):
        parent = previous[case['followup_of']]
        payload['history'] = parent['request'].get('history', []) + [
            {'role': 'user', 'content': parent['request']['q']},
            {'role': 'assistant', 'content': parent['answer']}]
    return payload


def portable_status(status):
    return {'llm': status.get('llm'), 'version': status.get('version'),
            'knowledge': status.get('knowledge'),
            'libraries': [{k: b.get(k) for k in ('name', 'served_name', 'archive_uuid', 'issued')}
                          for b in (status.get('kiwix') or {}).get('books', [])]}


def select_cases(manifest, group='all', case_ids=()):
    """Select without changing rubric bindings; include live-history ancestors."""
    by_id = {case['id']: case for case in manifest['cases']}
    requested = set(case_ids or ())
    unknown = requested - set(by_id)
    if unknown:
        raise ValueError('Unknown case IDs: ' + ', '.join(sorted(unknown)))
    eligible = {ident for ident, case in by_id.items()
                if group == 'all' or case['group'] == group}
    if requested - eligible:
        raise ValueError('Case IDs are outside the selected group')
    selected = requested or eligible
    pending = list(selected)
    while pending:
        parent = by_id[pending.pop()].get('followup_of')
        if parent and parent not in selected:
            selected.add(parent)
            pending.append(parent)
    return [case for case in manifest['cases'] if case['id'] in selected]


def run(args, manifest):
    selected = select_cases(manifest, args.group, getattr(args, 'case', ()))
    url = urlsplit(args.url)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise ValueError('Use an HTTP(S) app URL without credentials')
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    (out / 'raw').mkdir()
    metadata = {'started_at': now(), 'url': args.url, 'manifest_sha256': suite.digest(manifest),
                'deployment_identity': 'Not attested by API; version/model names are not file hashes',
                'trials': args.trials, 'timeout': args.timeout,
                'selected_case_ids': [case['id'] for case in selected],
                'harness_files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in HERE.glob('*.py')}}
    try:
        with build_opener(ProxyHandler({})).open(args.url.rstrip('/') + '/api/status', timeout=30) as response:
            status = json.load(response)
        write(out / 'raw/status.json', status)
        metadata['status'] = portable_status(status)
    except (OSError, ValueError) as exc:
        metadata['status_error'] = str(exc)
    if args.root:
        installation = Path(args.root) / 'runtime/installation.json'
        metadata['operator_supplied_root'] = str(Path(args.root).resolve())
        metadata['root_identity_limitation'] = 'Read-only manifest; API-to-directory mapping is operator supplied, not attested'
        if installation.exists():
            data = installation.read_bytes()
            metadata['installation_manifest_sha256'] = hashlib.sha256(data).hexdigest()
            metadata['installation_app_commit'] = json.loads(data).get('app', {}).get('commit')
    try:
        metadata['harness_commit'] = subprocess.check_output(
            ['git', '-C', str(HERE), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
        metadata['harness_dirty'] = bool(subprocess.check_output(
            ['git', '-C', str(HERE), 'status', '--porcelain'], text=True))
    except (OSError, subprocess.CalledProcessError):
        metadata['harness_commit'] = None
    write(out / 'manifest.json', manifest)
    write(out / 'metadata.json', metadata)
    results = []
    for trial in range(1, args.trials + 1):
        previous = {}
        for case in selected:
            payload = payload_for(case, previous)
            parent = previous.get(case.get('followup_of'))
            if parent and suite.normalize(parent)['outcome'] in ('error', 'incomplete', 'empty', 'unavailable'):
                raw = {'id': case['id'], 'request': payload, 'answer': '', 'events': [],
                       'error': 'Live follow-up parent failed; no invented conversation'}
            else:
                raw = ask(args.url, payload, case['id'], args.timeout)
            previous[case['id']] = raw
            raw_path = out / 'raw' / f"{case['id']}-{trial}.json"
            write(raw_path, raw)
            raw['raw_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            result = suite.normalize(raw, trial)
            results.append(result)
            # Each case is durable even if a later case is interrupted.
            write(out / f"{case['id']}-{trial}.json", result)
            print(suite.key(result), result['outcome'], flush=True)
    write(out / 'run.json', {'schema_version': 1, 'metadata': metadata, 'results': results})
    return 0 if all(r['outcome'] not in ('error', 'incomplete', 'empty', 'unavailable') for r in results) else 2


def import_run(args, manifest):
    folder = Path(args.directory)
    results = []
    for case in manifest['cases']:
        if case['group'] != 'historical':
            continue
        path = folder / (case['id'] + '.json')
        raw = read(path)
        if raw['request'] != case['request']:
            raise ValueError('Historical request changed: ' + case['id'])
        raw['raw_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        results.append(suite.normalize(raw))
    status = read(folder / 'status.json') if (folder / 'status.json').exists() else {}
    write(args.output, {'schema_version': 1, 'metadata': {'label': args.label,
          'imported_at': now(), 'manifest_sha256': suite.digest(manifest),
          'deployment_identity': 'Historical deployment unverified', 'status': portable_status(status),
          'normalization': 'Answer/request/sources/terminal generation retained; raw retrieval diagnostics omitted'},
          'results': results})
    return 0


def reviewed(path, results, manifest):
    if not path:
        return {}
    document = read(path)
    if document.get('review_manifest_sha256') != suite.digest(manifest):
        raise ValueError('Stale review manifest or reference catalog')
    return suite.load_reviews(document, results, manifest['cases'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default=str(HERE / 'cases.json'))
    commands = parser.add_subparsers(dest='command', required=True)
    live = commands.add_parser('run')
    live.add_argument('--url', default='http://127.0.0.1:8090')
    live.add_argument('--output', required=True)
    live.add_argument('--root', help='Optional read-only installation provenance; never modifies app')
    live.add_argument('--trials', type=int, default=1)
    live.add_argument('--timeout', type=float, default=240)
    live.add_argument('--case', action='append', default=[],
                      help='Case ID to run; repeat for multiple cases. Includes live conversation parents.')
    live.add_argument('--group', choices=['historical', 'boundary', 'live', 'all'], default='all')
    imp = commands.add_parser('import')
    imp.add_argument('--directory', required=True); imp.add_argument('--output', required=True)
    imp.add_argument('--label', required=True)
    template = commands.add_parser('template')
    template.add_argument('--run', required=True); template.add_argument('--output', required=True)
    for command in ('report', 'compare'):
        sub = commands.add_parser(command)
        sub.add_argument('--run', required=True); sub.add_argument('--reviews')
        sub.add_argument('--output', required=True)
        if command == 'compare':
            sub.add_argument('--before', required=True); sub.add_argument('--before-reviews')
    args = parser.parse_args(argv)
    try:
        manifest = cases_from(args.manifest)
        if args.command == 'run':
            if args.trials < 1 or args.timeout <= 0:
                raise ValueError('Trials and timeout must be positive')
            return run(args, manifest)
        if args.command == 'import':
            return import_run(args, manifest)
        results = read(args.run)['results']
        if len({suite.key(r) for r in results}) != len(results):
            raise ValueError('Duplicate case/trial result')
        if args.command == 'template':
            cases = {c['id']: c for c in manifest['cases']}
            write(args.output, {'review_manifest_sha256': suite.digest(manifest),
                                'reviews': [suite.review_template(r, cases[r['id']]) for r in results]})
            return 0
        reviews = reviewed(args.reviews, results, manifest)
        if args.command == 'compare':
            before = read(args.before)['results']
            old_reviews = reviewed(args.before_reviews, before, manifest)
            data = suite.compare(before, results, old_reviews, reviews)
            text = report.comparison(data)
        else:
            data = suite.summarize(results, reviews)
            text = report.render(results, reviews, data)
        output = Path(args.output)
        # JSON and Markdown are distinct artifacts; never silently replace either.
        if output.exists() or output.with_suffix('.json').exists():
            raise ValueError('Report output already exists')
        text += '\n\n## Reference catalog\n\n' + '\n'.join(f"- {ident}: [{ref['title']}]({ref['url']}) (checked {ref['checked_at']})" for ident, ref in manifest['references'].items()) + '\n'
        output.write_text(text, encoding='utf-8')
        write(output.with_suffix('.json'), data)
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print('Evaluation stopped: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
