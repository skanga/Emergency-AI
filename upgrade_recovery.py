"""Offline recovery; deliberately independent of the application and its imports."""
import argparse
from contextlib import contextmanager
from functools import partial
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import uuid
import sys

if __name__ == '__main__':
    sys.modules['upgrade_recovery'] = sys.modules[__name__]

_HELD_LOCKS = {}


def safe_path(root, name, internal=False, preserve_file_links=False):
    name = str(name)
    parts = PurePosixPath(name).parts
    if (not parts or name.startswith('/') or '\\' in name or ':' in name
            or any(p in ('..', '.git') for p in parts)
            or (not internal and parts[:2] == ('runtime', 'upgrades'))):
        raise ValueError('Unsafe upgrade path: ' + name)
    root = Path(root).resolve()
    path = root
    for index, part in enumerate(parts):
        path = path / part
        if path.is_symlink() and not (preserve_file_links and index == len(parts)-1):
            raise ValueError('Symlink in upgrade path: ' + name)
    return path


def digest(path, preserve_file_links=False):
    path = Path(path)
    if preserve_file_links and path.is_symlink():
        return "symlink:" + hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise ValueError('Expected ordinary file: ' + str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def file_mode(path):
    return stat.S_IMODE(Path(path).lstat().st_mode) if path is not None and (Path(path).exists() or Path(path).is_symlink()) else None


def matches_file(path, record, phase, git_mode=False, preserve_file_links=False,
                 allow_readonly_transition=False):
    if digest(path, preserve_file_links=preserve_file_links) != record[phase]:
        return False
    key = phase + '_mode'
    if key not in record:
        return True  # Recovery also accepts journals written before modes were recorded.
    actual, expected = file_mode(path), record[key]
    if (allow_readonly_transition and os.name == 'nt'
            and actual is not None and expected is not None and not expected & 0o222
            and actual & ~0o222 == expected):
        # A crash can occur between clearing Windows' read-only attribute and
        # replacing the file. Only interrupted recovery accepts this exact hash.
        return True
    if git_mode and actual is not None and expected is not None:
        return bool(actual & 0o111) == bool(expected & 0o111)
    return actual == expected


def _sync_dir(folder):
    if os.name != 'nt':
        fd = os.open(str(folder), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.journal-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        _sync_dir(path.parent)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def _activate(source, target, preserve_file_links=False):
    target = Path(target)
    if source is None:
        if target.exists() or target.is_symlink():
            _replace_or_remove(target)
            _sync_dir(target.parent)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.upgrade-', dir=str(target.parent))
    os.close(fd)
    try:
        if preserve_file_links and Path(source).is_symlink():
            os.unlink(temp)
            os.symlink(os.readlink(source), temp)
        else:
            with open(source, 'rb') as incoming, open(temp, 'wb') as stream:
                shutil.copyfileobj(incoming, stream)
                stream.flush()
                os.fsync(stream.fileno())
            shutil.copystat(source, temp)
        _replace_or_remove(target, temp)
        _sync_dir(target.parent)
    finally:
        if os.path.lexists(temp):
            _replace_or_remove(Path(temp))


def _replace_or_remove(target, source=None):
    # Windows refuses replacement/deletion of read-only files. Restore the
    # original attribute if replacement fails (for example, an open executable).
    mode = file_mode(target)
    readonly = os.name == 'nt' and mode is not None and not mode & stat.S_IWRITE
    if readonly:
        target.chmod(mode | stat.S_IWRITE)
    try:
        if source is None:
            target.unlink()
        else:
            os.replace(source, target)
    except OSError:
        if readonly:
            target.chmod(mode)
        raise


def _windows_lock(stream, shared=False, unlock=False):
    # CRT locking does not provide true shared reader locks. LockFileEx does.
    import ctypes
    from ctypes import wintypes
    import msvcrt

    class Overlapped(ctypes.Structure):
        _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                    ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                    ('hEvent', wintypes.HANDLE)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
    position = Overlapped()
    if unlock:
        function = kernel.UnlockFileEx
        function.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                             wintypes.DWORD, ctypes.POINTER(Overlapped)]
        args = (handle, 0, 1, 0, ctypes.byref(position))
    else:
        function = kernel.LockFileEx
        function.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                             wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
        args = (handle, 1 | (0 if shared else 2), 0, 1, 0, ctypes.byref(position))
    function.restype = wintypes.BOOL
    if not function(*args):
        raise ctypes.WinError(ctypes.get_last_error())


@contextmanager
def maintenance_lock(root, shared=False, reuse=False):
    key = str(Path(root).resolve())
    if reuse and key in _HELD_LOCKS:
        if not shared and _HELD_LOCKS[key]:
            raise RuntimeError('Cannot upgrade a running application; restart in maintenance mode')
        yield
        return
    path = safe_path(root, 'runtime/upgrades/maintenance.lock', internal=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                _windows_lock(stream, shared=shared)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('Another maintenance/start operation is active') from exc
        try:
            _HELD_LOCKS[key] = shared
            yield
        finally:
            _HELD_LOCKS.pop(key, None)
            if os.name == 'nt':
                _windows_lock(stream, unlock=True)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def pending(root):
    folder = safe_path(root, 'runtime/upgrades', internal=True)
    result = []
    for path in sorted(folder.glob('*/journal.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['state'] in ('activating', 'checking', 'rolling_back', 'recovery_failed'):
            result.append(path.parent.name)
    return result


class Transaction:
    def __init__(self, root, component, preserve_file_links=False):
        self.root = Path(root).resolve()
        self.id = uuid.uuid4().hex
        self.folder = safe_path(root, 'runtime/upgrades/' + self.id, internal=True)
        self.folder.mkdir(parents=True)
        shutil.copy2(__file__, self.folder / 'recover.py')
        self.data = {'schema_version': 1, 'id': self.id, 'component': component,
                     'state': 'planned', 'files': [], 'advice_evaluation': 'not_run',
                     'preserve_file_links': bool(preserve_file_links)}
        self.save()

    def save(self):
        atomic_json(self.folder / 'journal.json', self.data)

    def apply(self, changes, verify=None):
        # Caller owns the maintenance lock across staging, activation and checks.
        if self.data['state'] != 'planned':
            raise ValueError('Transaction has already been applied')
        preserve = self.data.get('preserve_file_links', False)
        path_for = partial(safe_path, preserve_file_links=preserve)
        hash_file = partial(digest, preserve_file_links=preserve)
        matches = partial(matches_file, preserve_file_links=preserve)
        activate = partial(_activate, preserve_file_links=True) if preserve else _activate
        records = []
        needed = 0
        for name, source in changes.items():
            target = path_for(self.root, name)
            before, after = hash_file(target), hash_file(source) if source is not None else None
            if source is not None and after is None:
                raise ValueError('Staged file is missing: ' + str(source))
            before_mode, after_mode = file_mode(target), file_mode(source)
            if before == after and before_mode == after_mode:
                continue
            needed += (target.lstat().st_size if before else 0) + (Path(source).stat().st_size * 2 if after else 0)
            records.append({'path': name, 'before': before, 'after': after,
                            'before_mode': before_mode, 'after_mode': after_mode})
        if shutil.disk_usage(self.root).free < needed + 1024 * 1024:
            raise OSError('Insufficient space for staged files and rollback backups')
        for record in records:
            name = record['path']
            if record['before']:
                activate(path_for(self.root, name), path_for(self.folder / 'before', name))
            if record['after']:
                activate(changes[name], path_for(self.folder / 'after', name))
            # Verify backups before changing any installed path.
            if not matches(path_for(self.folder / 'before', name), record, 'before'):
                raise ValueError('Backup verification failed: ' + name)
            if not matches(path_for(self.folder / 'after', name), record, 'after'):
                raise ValueError('Staged verification failed: ' + name)
        self.data.update(files=records, state='verified')
        self.save()
        for record in records:
            if not matches(path_for(self.root, record['path']), record, 'before'):
                raise ValueError('File changed during preparation: ' + record['path'])
        self.data['state'] = 'activating'
        self.save()
        try:
            for record in records:
                source = path_for(self.folder / 'after', record['path']) if record['after'] else None
                activate(source, path_for(self.root, record['path']))
            self.data['state'] = 'checking'
            self.save()
            if verify:
                verify()
            self.data['state'] = 'committed'
            self.save()
        except Exception:
            try:
                rollback(self.root, self.id)
            except Exception:
                self.data['state'] = 'recovery_failed'
                self.save()
                raise
            raise
        return self.id


def rollback(root, transaction_id):
    if not re.fullmatch(r'[a-f0-9]{32}', transaction_id):
        raise ValueError('Invalid transaction ID')
    folder = safe_path(root, 'runtime/upgrades/' + transaction_id, internal=True)
    data = json.loads((folder / 'journal.json').read_text(encoding='utf-8'))
    if data.get('kind') == 'git':
        return _rollback_git(root, folder, data)
    if data['state'] == 'rolled_back':
        return transaction_id
    preserve = data.get('preserve_file_links', False)
    path_for = partial(safe_path, preserve_file_links=preserve)
    matches = partial(matches_file, preserve_file_links=preserve)
    activate = partial(_activate, preserve_file_links=True) if preserve else _activate
    # Preflight every path before restoring any. Both states are legitimate after a crash.
    for record in data['files']:
        current = path_for(root, record['path'])
        interrupted = data['state'] != 'committed'
        if not any(matches(current, record, phase, allow_readonly_transition=interrupted)
                   for phase in ('before', 'after')):
            raise ValueError('File changed since upgrade: ' + record['path'])
        if not matches(path_for(folder / 'before', record['path']), record, 'before'):
            raise ValueError('Corrupt or missing backup: ' + record['path'])
    data['state'] = 'rolling_back'
    atomic_json(folder / 'journal.json', data)
    for record in reversed(data['files']):
        source = path_for(folder / 'before', record['path']) if record['before'] else None
        activate(source, path_for(root, record['path']))
    data['state'] = 'rolled_back'
    atomic_json(folder / 'journal.json', data)
    return transaction_id


def _rollback_git(root, folder, data):
    import subprocess
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root)] + list(args), text=True,
                                       stderr=subprocess.STDOUT).rstrip('\n')
    if data['state'] == 'rolled_back':
        return data['id']
    index = Path(git('rev-parse', '--git-path', 'index'))
    if not index.is_absolute():
        index = Path(root) / index
    if index.is_symlink():
        raise ValueError('Git index must not be a symlink')
    lock = index.with_name(index.name + '.lock')
    try:
        stream = lock.open('xb')
    except FileExistsError as exc:
        raise RuntimeError('Git index is locked; finish the other Git operation before recovery') from exc
    owns_lock = True
    try:
        with stream:
            if data['state'] == 'committed' and git('status', '--porcelain', '--untracked-files=no'):
                raise ValueError('Git files changed since upgrade; preserve edits before rollback')
            head = git('rev-parse', 'HEAD')
            if head not in (data['before_commit'], data['after_commit']):
                raise ValueError('Git HEAD changed since upgrade')
            if git('symbolic-ref', '--short', 'HEAD') != data['branch']:
                raise ValueError('Git branch changed since upgrade')
            # These commands only read the index, so our lock remains held throughout.
            indexed = []
            for entry in git('ls-files', '--stage', '-z').split('\0'):
                if entry:
                    metadata, name = entry.split('\t', 1)
                    mode, oid, stage = metadata.split()
                    if stage != '0':
                        raise ValueError('Git index contains unresolved conflicts')
                    indexed.append((name, mode, oid))
            trees = []
            for commit in (data['before_commit'], data['after_commit']):
                tree = []
                for entry in git('ls-tree', '-r', '-z', commit).split('\0'):
                    if entry:
                        metadata, name = entry.split('\t', 1)
                        mode, kind, oid = metadata.split()
                        tree.append((name, mode, oid))
                trees.append(sorted(tree))
            if sorted(indexed) not in trees:
                raise ValueError('Git index changed since upgrade')
            if digest(folder / 'git-index') != data['index_hash']:
                raise ValueError('Corrupt Git index backup')
            for record in data['files']:
                current = safe_path(root, record['path'])
                allowed = ('after',) if data['state'] == 'committed' else ('before', 'after')
                if not any(matches_file(current, record, phase, git_mode=True,
                                        allow_readonly_transition=data['state'] != 'committed')
                           for phase in allowed):
                    raise ValueError('File changed or untracked collision since upgrade: ' + record['path'])
                if not matches_file(safe_path(folder / 'before', record['path']), record, 'before'):
                    raise ValueError('Corrupt Git file backup: ' + record['path'])
            data['state'] = 'rolling_back'
            atomic_json(folder / 'journal.json', data)
            for record in reversed(data['files']):
                source = safe_path(folder / 'before', record['path']) if record['before'] else None
                _activate(source, safe_path(root, record['path']))
            with (folder / 'git-index').open('rb') as backup:
                shutil.copyfileobj(backup, stream)
            stream.flush()
            os.fsync(stream.fileno())
            git('update-ref', 'refs/heads/' + data['branch'], data['before_commit'], head)
        os.replace(lock, index)
        owns_lock = False
        _sync_dir(index.parent)
        data['state'] = 'rolled_back'
        atomic_json(folder / 'journal.json', data)
    finally:
        if owns_lock:
            lock.unlink()
    return data['id']


def recovery_command(root, transaction):
    import shlex
    import subprocess
    root = Path(root).resolve()
    recovery = [sys.executable, str(root / 'runtime/upgrades' / transaction / 'recover.py'),
                '--root', str(root), '--rollback', transaction]
    return subprocess.list2cmdline(recovery) if os.name == 'nt' else shlex.join(recovery)


def ensure_stopped(root):
    import socket
    settings = {}
    for name in ('config/settings.json', 'config/settings.local.json'):
        path = safe_path(root, name)
        if path.exists():
            settings.update(json.loads(path.read_text(encoding='utf-8')))
    for key, default in (('web_port', 8090), ('llm_port', 8091), ('kiwix_port', 8092)):
        port = int(settings.get(key, default))
        if port == 0:
            continue
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                raise RuntimeError('Port %s is active. Stop the app and local services before maintenance; no process was stopped.' % port)
        except (ConnectionRefusedError, socket.timeout):
            pass


def launch(argv, root=None):
    """Take the installation lock before importing any application modules."""
    import runpy
    root = Path(root or Path(__file__).resolve().parent)
    argv = list(argv)
    command = argv[0] if argv else ''
    if command in ('--rollback', 'rollback'):
        parser = argparse.ArgumentParser(description='Offline transaction recovery')
        parser.add_argument('transaction_id')
        parser.add_argument('--root', default=str(root))
        args = parser.parse_args(argv[1:])
        root = Path(args.root).expanduser().resolve()
        try:
            with maintenance_lock(root):
                ensure_stopped(root)
                rollback(root, args.transaction_id)
            print('Restored transaction ' + args.transaction_id)
            return 0
        except (OSError, ValueError, RuntimeError) as exc:
            print('Recovery stopped: ' + str(exc))
            return 1
    commands = ('--plan-migration', 'plan-migration', '--apply-migration', 'apply-migration', '--upgrade', 'upgrade', '--adopt', 'adopt', '--check-updates', 'check-updates',
                'prepare', 'index-libraries', 'chat', 'ask', 'search', 'status', 'diagnose-retrieval', 'start')
    command = next((c for c in argv if c in commands), 'start')
    maintenance = command in ('--apply-migration', 'apply-migration', '--upgrade', 'upgrade', '--adopt', 'adopt', 'prepare', 'index-libraries')
    ordinary_start = command == 'start' and not any(c in argv for c in ('--help', '-h'))
    # Windows NUL can report isatty(); match startup's visible-terminal check.
    if (ordinary_start and '--no-update-check' not in argv
            and sys.stdin.isatty() and sys.stdout.isatty()):
        try:
            with maintenance_lock(root):
                if pending(root):
                    raise RuntimeError('Recover interrupted transaction: ' + ', '.join(pending(root)))
                from app.upgrade_cli import _settings, startup
                startup(root, _settings(root))
        except (OSError, ValueError, RuntimeError) as exc:
            print('Pre-start update check skipped: ' + str(exc))
        arguments = [sys.executable, str(root / 'emergency.py'), *argv, '--no-update-check']
        if sys.platform == 'win32':
            # The Windows CRT exec API joins arguments without quoting them.
            import subprocess
            arguments = [subprocess.list2cmdline([arg]) for arg in arguments]
        os.execv(sys.executable, arguments)
    try:
        with maintenance_lock(root, shared=not maintenance):
            unfinished = pending(root)
            if unfinished:
                print('Recover interrupted upgrade: ' + recovery_command(root, unfinished[0]))
                return 1
            sys.argv = [str(root / 'emergency.py')] + argv
            try:
                runpy.run_path(str(root / 'emergency.py'), init_globals={'_UPGRADE_BOOTSTRAP': True}, run_name='__main__')
            except SystemExit as exc:
                return exc.code or 0
            return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print('Launch stopped: ' + str(exc))
        return 1


def main():
    if sys.argv[1:2] == ['--launch']:
        return launch(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--rollback')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        if args.check:
            unfinished = pending(args.root)
            if unfinished:
                print('Interrupted upgrade: ' + ', '.join(unfinished) + '. Run --rollback ID before starting.')
                return 1
            return 0
        if not args.rollback:
            parser.error('--rollback ID or --check required')
        with maintenance_lock(args.root):
            ensure_stopped(args.root)
            rollback(args.root, args.rollback)
        print('Restored transaction ' + args.rollback)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print('Recovery failed: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
