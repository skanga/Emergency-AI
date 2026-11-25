"""Application-only upgrades for Git checkouts and manifest-owned standalone files."""
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

from upgrade_recovery import Transaction, _activate, atomic_json, digest, file_mode, rollback, safe_path


def managed(name):
    parts = Path(name).parts
    if any(p in ('.git', '__pycache__', '.venv', '.agents', '.codex') for p in parts):
        return False
    if name == 'config/settings.local.json' or name.startswith('knowledge/extra/'):
        return False
    if parts[0] in ('runtime', 'models', 'zim', 'logs', 'output', 'indexes'):
        return len(parts) == 2 and parts[1].startswith('README')
    return not name.endswith(('.pyc', '.log'))


def file_manifest(root):
    result = {}
    root = Path(root)
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv', '.agents', '.codex')]
        for filename in files:
            path = Path(folder) / filename
            name = path.relative_to(root).as_posix()
            if managed(name):
                result[name] = digest(safe_path(root, name))
    return result


def verify_source(root):
    root = Path(root)
    for name in file_manifest(root):
        path = root / name
        if path.suffix == '.py':
            ast.parse(path.read_bytes(), filename=name)
        elif name.startswith('config/') and path.suffix == '.json':
            json.loads(path.read_text(encoding='utf-8'))


def health(root):
    # Parent owns the exclusive maintenance lease; this bounded child is its probe.
    probe = "import runpy,sys; p=sys.argv[1]; sys.argv=[p,'--help']; runpy.run_path(p, init_globals={'_UPGRADE_BOOTSTRAP':True}, run_name='__main__')"
    subprocess.run([sys.executable, '-B', '-c', probe, str(Path(root) / 'emergency.py')],
                   cwd=str(root), check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, timeout=30)


def apply_standalone(root, fresh, commit, baseline=None, verify=None, preserved_files=None):
    root, fresh = Path(root), Path(fresh)
    if not isinstance(commit, str) or not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Expected immutable application commit')
    manifest_path = safe_path(root, 'runtime/installation.json')
    installed = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if preserved_files is None:
        preserved_files = installed.get('app', {}).get('preserved_files', [])
    for name in preserved_files:
        if not name.startswith(('config/', 'knowledge/')):
            raise ValueError('Invalid preserved application path: ' + name)
        safe_path(root, name)
    previous = installed.get('app', {}).get('files')
    if previous is None:
        previous = baseline
    if previous is None:
        raise ValueError('Unknown standalone baseline; supply --baseline COMMIT to verify existing owned files')
    verify_source(fresh)
    following = {name: sha for name, sha in file_manifest(fresh).items() if name not in preserved_files}
    for name, sha in previous.items():
        if not managed(name):
            raise ValueError('Protected file in baseline: ' + name)
        if digest(safe_path(root, name)) != sha:
            raise ValueError('Locally modified or deleted owned file: ' + name)
    for name in following:
        if name not in previous and safe_path(root, name).exists():
            raise ValueError('Untracked file collision: ' + name)
    changes = {name: fresh / name if name in following else None for name in set(previous) | set(following)}
    installed.update(schema_version=1, app={'commit': commit, 'files': following, 'preserved_files': sorted(preserved_files)})
    with tempfile.TemporaryDirectory(prefix='app-manifest-') as tmp:
        new_manifest = Path(tmp) / 'installation.json'
        atomic_json(new_manifest, installed)
        changes['runtime/installation.json'] = new_manifest
        tx = Transaction(root, 'app')
        return tx.apply(changes, verify=verify or (lambda: health(root)))


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root)] + list(args), text=True,
                                   stderr=subprocess.STDOUT, timeout=120).strip()


def apply_git(root, commit, verify=None):
    if not isinstance(commit, str) or not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Expected immutable application commit')
    if git(root, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Git tracked files are modified; commit or preserve edits before upgrading')
    branch = git(root, 'symbolic-ref', '--short', 'HEAD')
    before = git(root, 'rev-parse', 'HEAD')
    try:
        git(root, 'merge-base', '--is-ancestor', before, commit)
    except subprocess.CalledProcessError as exc:
        raise ValueError('Git history diverged; automatic update requires a fast-forward') from exc
    if before == commit:
        return None
    before_names = set(git(root, 'ls-tree', '-r', '--name-only', '-z', before).split('\0')) - {''}
    after_names = set(git(root, 'ls-tree', '-r', '--name-only', '-z', commit).split('\0')) - {''}
    changed_names = set(git(root, 'diff', '--no-renames', '--name-only', '-z', before, commit).split('\0')) - {''}
    for name in changed_names:
        if not managed(name):
            raise ValueError('Protected installation path changed in candidate: ' + name)
    for name in after_names:
        path = safe_path(root, name)
        if name not in before_names and path.exists():
            raise ValueError('Untracked or ignored file collision: ' + name)
    tx = Transaction(root, 'app')
    # Keep file and index snapshots, because Git checkout itself is not atomic.
    with tempfile.TemporaryDirectory(prefix='app-git-stage-') as tmp:
        archive = Path(tmp) / 'source.tar'
        git(root, 'archive', '--format=tar', '--output=' + str(archive), commit)
        fresh = Path(tmp) / 'source'
        extract_source(archive, fresh, strip_root=False)
        verify_source(fresh)
        records = []
        for name in sorted(before_names | after_names):
            current = safe_path(root, name)
            old_hash, new_hash = digest(current), digest(safe_path(fresh, name))
            before_mode, after_mode = file_mode(current), file_mode(fresh / name)
            same_mode = (before_mode is None and after_mode is None) or (
                before_mode is not None and after_mode is not None
                and bool(before_mode & 0o111) == bool(after_mode & 0o111))
            if old_hash == new_hash and same_mode:
                continue
            records.append({'path': name, 'before': old_hash, 'after': new_hash,
                            'before_mode': before_mode, 'after_mode': after_mode})
            if old_hash:
                _activate(current, safe_path(tx.folder / 'before', name))
            if new_hash:
                _activate(fresh / name, safe_path(tx.folder / 'after', name))
    index = Path(git(root, 'rev-parse', '--git-path', 'index'))
    if not index.is_absolute():
        index = Path(root) / index
    _activate(index, tx.folder / 'git-index')
    git(root, 'update-ref', 'refs/emergency-ai/backups/' + tx.id, before)
    tx.data.update(kind='git', before_commit=before, after_commit=commit, branch=branch,
                   files=records, index_hash=digest(tx.folder / 'git-index'), state='activating')
    tx.save()
    try:
        git(root, '-c', 'core.hooksPath=', 'merge', '--ff-only', '--no-edit', '--no-overwrite-ignore', commit)
        tx.data['state'] = 'checking'
        tx.save()
        (verify or (lambda: health(root)))()
        tx.data['state'] = 'committed'
        tx.save()
    except Exception:
        rollback(root, tx.id)
        raise
    return tx.id


def extract_source(archive, destination, strip_root=True):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 256 * 1024 * 1024:
            raise ValueError('Application archive is too large')
        for item in members:
            name = item.name
            # Validate the original path before stripping its root.
            safe_path(destination, name)
            if strip_root:
                name = name.partition('/')[2]
            if not name:
                continue
            path = safe_path(destination, name)
            if item.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif item.isfile():
                if path.exists():
                    raise ValueError('Duplicate source path: ' + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(item) as stream, path.open('wb') as out:
                    shutil.copyfileobj(stream, out)
                path.chmod(item.mode & 0o755)
            else:
                raise ValueError('Application archive contains a link or special file')


def stage_source(commit, destination):
    from .net import get_bytes
    if not isinstance(commit, str) or not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Expected immutable source commit')
    raw = get_bytes('https://codeload.github.com/skanga/Emergency-AI/tar.gz/' + commit,
                    timeout=60, max_bytes=64 * 1024 * 1024)
    archive = Path(destination).parent / (commit + '.tar.gz')
    archive.write_bytes(raw)
    extract_source(archive, destination)
    return file_manifest(destination)


def upgrade(root, candidate, baseline_commit=None):
    commit = candidate['commit']
    if candidate['kind'] == 'git':
        # Fetch configured upstream, then apply exactly the previously offered commit.
        remote = git(root, 'config', '--get', 'branch.' + git(root, 'symbolic-ref', '--short', 'HEAD') + '.remote')
        git(root, 'fetch', '--no-tags', remote, commit)
        return apply_git(root, commit)
    with tempfile.TemporaryDirectory(prefix='app-upgrade-') as tmp:
        fresh = Path(tmp) / 'fresh'
        stage_source(commit, fresh)
        baseline = stage_source(baseline_commit, Path(tmp) / 'baseline') if baseline_commit else None
        return apply_standalone(root, fresh, commit, baseline)
