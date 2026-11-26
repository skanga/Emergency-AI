"""Reviewable, pinned-source normalization of legacy standalone installations."""
import json
import re
from pathlib import Path

from upgrade_recovery import digest, file_mode, safe_path
from .upgrade_app import apply_standalone, file_manifest, verify_source


def build_plan(root, fresh, commit):
    root, fresh = Path(root).resolve(), Path(fresh)
    if not isinstance(commit, str) or not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Migration requires an immutable 40-character commit')
    if (root/'.git').exists():
        raise ValueError('Migration is for standalone installations, not Git checkouts')
    metadata = safe_path(root, 'runtime/installation.json')
    installed = json.loads(metadata.read_text()) if metadata.exists() else {}
    if not isinstance(installed, dict) or not isinstance(installed.get('app', {}), dict):
        raise ValueError('Invalid installed application manifest')
    if installed.get('app', {}).get('files') is not None:
        raise ValueError('Application already has an owned-file baseline; use normal app upgrade')
    verify_source(fresh)
    following = file_manifest(fresh)
    preserved = set()
    for folder in ('config', 'knowledge'):
        for path in (root/folder).rglob('*'):
            if path.is_file() or path.is_symlink():
                name = path.relative_to(root).as_posix()
                safe_path(root, name)
                preserved.add(name)
    rows = {}
    for name in sorted(set(following) | preserved):
        current = safe_path(root, name)
        before = digest(current)
        after = following.get(name)
        action = ('preserve' if name in preserved else 'add' if before is None else
                  'unchanged' if before == after and file_mode(current) == file_mode(fresh/name) else 'replace')
        rows[name] = {'action': action, 'before': before, 'before_mode': file_mode(current),
                      'after': after, 'after_mode': file_mode(fresh/name)}
    return {'schema_version': 1, 'root': str(root), 'commit': commit,
            'manifest_before': digest(metadata), 'manifest_mode': file_mode(metadata),
            'preserved_files': sorted(preserved), 'files': rows}


def apply_plan(root, fresh, plan, verify=None):
    expected = build_plan(root, fresh, plan.get('commit', ''))
    if plan != expected:
        raise ValueError('Migration plan no longer matches source or installation; create and review a new plan')
    previous = {name: row['before'] for name, row in plan['files'].items()
                if row['action'] != 'preserve' and row['before'] is not None}
    return apply_standalone(root, fresh, plan['commit'], baseline=previous,
                            preserved_files=plan['preserved_files'], verify=verify)


def describe(plan):
    lines = ['Standalone migration to ' + plan['commit'], 'Target: ' + plan['root']]
    for action in ('replace', 'add', 'preserve', 'unchanged'):
        names = [name for name, row in plan['files'].items() if row['action'] == action]
        lines.append(f'{action.capitalize()}: {len(names)}')
        if action != 'unchanged':
            lines.extend('  ' + name for name in names)
    lines.append('Unrelated local files stay in place. Replaced files are retained for offline rollback.')
    return '\n'.join(lines)


def run(root, args):
    import sys
    import tempfile
    from upgrade_recovery import ensure_stopped, maintenance_lock, pending
    from .upgrade_app import stage_source
    planning = args.command == 'plan-migration'
    with maintenance_lock(root, shared=planning, reuse=True):
        if pending(root):
            raise ValueError('Recover interrupted transactions before migration')
        if planning:
            output = Path(args.output).expanduser().absolute()
            if output.resolve() == Path(root).resolve() or Path(root).resolve() in output.resolve().parents:
                raise ValueError('Write the review plan outside the target installation')
            commit = args.commit
        else:
            ensure_stopped(root)
            with Path(args.plan).open('rb') as stream:
                raw = stream.read(8*1024*1024+1)
            if len(raw) > 8*1024*1024:
                raise ValueError('Migration plan is too large')
            plan = json.loads(raw)
            if not isinstance(plan, dict):
                raise ValueError('Invalid migration plan')
            commit = plan.get('commit', '')
        with tempfile.TemporaryDirectory(prefix='app-migration-') as temp:
            fresh = Path(temp)/'source'
            stage_source(commit, fresh)
            expected = build_plan(root, fresh, commit)
            if planning:
                # Exclusive creation avoids overwriting an existing review or other file.
                with output.open('x', encoding='utf-8') as stream:
                    json.dump(expected, stream, indent=2)
                    stream.write('\n')
                print(describe(expected))
                print('Review plan written to ' + str(output))
                return 0
            if expected != plan:
                raise ValueError('Migration plan no longer matches source or installation; create and review a new plan')
            print(describe(plan))
            if not args.yes:
                if not sys.stdin.isatty():
                    raise ValueError('Noninteractive migration requires --yes with a reviewed plan')
                if input('Back up and apply this migration? [y/N] ').strip().lower() not in ('y', 'yes'):
                    print('No changes made.')
                    return 0
            transaction = apply_plan(root, fresh, plan)
            from .upgrade_cli import recovery_command
            print('Migration applied. Offline rollback: ' + recovery_command(root, transaction))
            print('Restart with the target installation launcher. Preserved config/knowledge may differ from the recorded source commit.')
            return 0
