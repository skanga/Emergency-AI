"""Explicit upgrade selection and optional, bounded pre-start checks."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from .updates import check
from upgrade_recovery import atomic_json, ensure_stopped, maintenance_lock, pending, rollback, safe_path

COMPONENTS = ('app', 'model', 'llama', 'python', 'kiwix-tools', 'document-tools', 'kiwix-data', 'drivers')
ALIASES = {'--upgrade': 'upgrade', '--check-updates': 'check-updates', '--rollback': 'rollback', '--adopt': 'adopt', '--plan-migration': 'plan-migration', '--apply-migration': 'apply-migration'}


def _settings(root):
    settings = {}
    for name in ('config/settings.json', 'config/settings.local.json'):
        path = Path(root) / name
        if path.exists():
            settings.update(json.loads(path.read_text(encoding='utf-8')))
    return settings


def show(report):
    print('Update check: ' + report.get('checked_at', 'unknown time'))
    for row in report['components']:
        old = row.get('installed') or {}
        new = row.get('candidate') or {}
        installed = old.get('commit') or old.get('revision') or old.get('tag') or old.get('file') or old.get('version') or old.get('asset') or 'unknown'
        candidate = new.get('identity') or 'unknown'
        size = ('; download %s bytes' % new['size']) if new.get('size') and row['status']=='available' else ''
        label = row['component']
        if old.get('platform'):
            label += ' [' + old['platform'] + ('/' + old['backend'] if old.get('backend') else '') + ']'
        print('  %s: %s — %s -> %s%s' % (label, row['status'], installed, candidate, size))
        print('    ' + row['reason'])


def apply_record(root, record, baseline=None):
    if record['component'] == 'app':
        from .upgrade_app import upgrade
        return upgrade(root, record['candidate'], baseline_commit=baseline)
    from .upgrade_assets import upgrade
    return upgrade(root, record)


def _selected(report, components, baseline):
    rows = [r for r in report['components'] if r['component'] in components]
    found = {r['component'] for r in rows}
    if found != set(components):
        raise ValueError('No inventory for: ' + ', '.join(set(components) - found))
    candidates, skipped = [], []
    for row in rows:
        if row['status'] == 'current':
            continue
        adopting = baseline and row['component'] == 'app' and (row.get('candidate') or {}).get('kind') == 'standalone'
        if row['status'] != 'available' and not adopting:
            skipped.append(row)
            continue
        candidates.append(row)
    for component in components:
        component_rows = [r for r in rows if r['component'] == component]
        if not any(r in candidates or r['status'] == 'current' for r in component_rows):
            raise ValueError('%s cannot be upgraded automatically: %s' % (component, component_rows[0]['reason']))
    for row in skipped:
        print('Leaving %s unchanged (%s): %s' % (row['component'], (row.get('installed') or {}).get('path', 'unknown'), row['reason']))
    return candidates


def perform(root, report, components, yes=False, baseline=None):
    rows = _selected(report, components, baseline)
    if not rows:
        print('Selected components are current.')
        return False
    labels = []
    for row in rows:
        label = row['component']
        backend = (row.get('installed') or {}).get('backend')
        if label == 'llama' and backend:
            label += ' (' + ('Vulkan' if backend == 'vulkan' else backend.upper()) + ')'
        labels.append(label)
    print('Selected: ' + ', '.join(labels))
    print('Previous files will be retained under runtime/upgrades. Advice quality evaluation: not run.')
    if not yes:
        if not sys.stdin.isatty():
            raise ValueError('Noninteractive upgrades require explicit --component and --yes')
        if input('Download, verify and apply these updates? [y/N] ').strip().lower() not in ('y', 'yes'):
            print('No changes made.')
            return False
    with maintenance_lock(root, reuse=True):
        if pending(root):
            raise ValueError('Recover the interrupted transaction before upgrading: ' + ', '.join(pending(root)))
        ensure_stopped(root)
        for row in rows:
            transaction = apply_record(root, row, baseline)
            print('%s updated. Rollback: ./run.sh --rollback %s' % (row['component'], transaction))
            # Do not run old imported modules against a newly replaced application.
            if row['component'] in ('app', 'python') and row is not rows[-1]:
                print('Restart the upgrade command to recheck remaining components using the new application.')
                break
    return True


def main(argv=None, root=None):
    from .config import ROOT
    root = Path(root or ROOT)
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        argv[0] = ALIASES.get(argv[0], argv[0])
    parser = argparse.ArgumentParser(description='Check, upgrade or recover individual Emergency AI components.')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('check-updates', help='read-only online inventory and update report')
    p.add_argument('--root', help='explicit target installation')
    p.add_argument('--json', action='store_true')
    p.add_argument('--timeout', type=float, default=30)
    p = sub.add_parser('upgrade', help='select, stage, verify and back up component updates')
    p.add_argument('--root', help='explicit target installation, including an older standalone kit')
    p.add_argument('--component', choices=COMPONENTS, action='append')
    p.add_argument('--yes', action='store_true')
    p.add_argument('--baseline', help='immutable original app commit for legacy standalone baseline verification')
    p = sub.add_parser('rollback', help='offline restoration of a retained transaction')
    p.add_argument('--root', help='explicit target installation')
    p.add_argument('transaction_id')
    p = sub.add_parser('adopt', help='verify existing assets/tools and record provenance without replacing installed files')
    p.add_argument('--root', help='explicit target installation')
    p.add_argument('--component', choices=('model', 'kiwix-data', 'kiwix-tools', 'document-tools'), action='append', required=True)
    p = sub.add_parser('plan-migration', help='preview a pinned-source migration of a legacy standalone kit')
    p.add_argument('--root')
    p.add_argument('--commit', required=True)
    p.add_argument('--output', required=True, help='new review plan file outside the target kit')
    p = sub.add_parser('apply-migration', help='apply an unchanged reviewed migration plan with backups')
    p.add_argument('--root')
    p.add_argument('plan')
    p.add_argument('--yes', action='store_true')
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve() if args.root else root
    try:
        if not root.is_dir():
            raise ValueError('Target installation directory does not exist')
        if args.command in ('plan-migration', 'apply-migration'):
            from .upgrade_migration import run
            return run(root, args)
        if args.command == 'adopt':
            from .upgrade_inventory import adopt
            with maintenance_lock(root, reuse=True):
                if pending(root):
                    raise ValueError('Recover pending transactions before adopting files')
                if set(args.component) & {'kiwix-tools','document-tools'}:
                    ensure_stopped(root)
                result = adopt(root, args.component)
            print(json.dumps(result, indent=2))
            return 1 if result['unknown'] else 0
        if args.command == 'rollback':
            with maintenance_lock(root, reuse=True):
                ensure_stopped(root)
                rollback(root, args.transaction_id)
            print('Restored ' + args.transaction_id)
            return 0
        if args.command == 'upgrade' and not args.component and (args.yes or not sys.stdin.isatty()):
            raise ValueError('Select components explicitly with --component; no implicit update-all')
        with maintenance_lock(root, shared=True, reuse=True):
            result = check(root, timeout=args.timeout if args.command == 'check-updates' else 30,
                           components=args.component if args.command == 'upgrade' else None)
        if getattr(args, 'json', False):
            print(json.dumps(result, indent=2))
        else:
            show(result)
        if args.command == 'check-updates':
            return 0
        components = args.component
        if components is None:
            answer = input('Components to upgrade, comma-separated (Enter to exit): ').strip()
            if not answer:
                return 0
            components = [c.strip() for c in answer.split(',')]
            if any(c not in COMPONENTS for c in components):
                raise ValueError('Unknown component selection')
        perform(root, result, components, yes=args.yes, baseline=args.baseline)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('Upgrade stopped: ' + str(exc), file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print('Cancelled. If activation was interrupted, the next launch will require recovery.')
        return 1


def startup(root, settings):
    """Return True if a fresh process is needed. Failed checks never prevent startup."""
    if not sys.stdin.isatty() or not settings.get('check_updates_on_start', True):
        return False
    try:
        cache = safe_path(root, 'runtime/update-check.json')
        if cache.exists() and 0 <= time.time() - cache.stat().st_mtime < 86400:
            return False
        print('Checking for updates (up to 5 seconds; offline startup remains available)...')
        result = check(root, timeout=5)
        atomic_json(cache, result)
        available = [r for r in result['components'] if r['status'] == 'available']
        if not available:
            print('No available updates found. Unavailable/unknown components are not confirmed current.')
            return False
        show(result)
        answer = input('Start now [Enter], or type component names to upgrade: ').strip()
        if not answer:
            return False
        return perform(root, result, [c.strip() for c in answer.split(',')])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, EOFError) as exc:
        print('Update check/upgrade skipped: %s' % exc)
        if pending(root):
            raise RuntimeError('An interrupted upgrade needs recovery before startup')
        return False
