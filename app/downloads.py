"""Resumable downloads, integrity checks and safe archive extraction.

No component catalogs or installer orchestration belong in this module.
"""
import hashlib
import os
import posixpath
import re
import shutil
import subprocess
import stat
import tempfile
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile

from .net import USER_AGENT


def _require_https(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Downloads require an HTTPS URL")


class _HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_HTTPS_OPENER = urllib.request.build_opener(_HTTPSRedirectHandler())


# ---------------------------------------------------------------- download
def _human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _file_valid(path, expected_size=None, sha256=None):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return False
    if expected_size is not None and os.path.getsize(path) != expected_size:
        return False
    if sha256:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        if h.hexdigest().lower() != sha256.lower():
            return False
    return True


def _zim_checksum_valid(path):
    """Check the ZIM header and embedded MD5 for accidental corruption, not authenticity."""
    with open(path, "rb") as f:
        header = f.read(80)
        if (len(header) != 80 or header[:4] != b"ZIM\x04"
                or int.from_bytes(header[4:6], "little") not in (5, 6)
                or int.from_bytes(header[56:64], "little") != 80):
            return False
        remaining = int.from_bytes(header[72:80], "little")
        if remaining < 80 or remaining + 16 != os.path.getsize(path):
            return False
        print("  Checking ZIM integrity (reads the whole file; large archives may take several minutes)...")
        digest = hashlib.md5()
        f.seek(0)
        while remaining:
            block = f.read(min(1 << 20, remaining))
            if not block:
                return False
            digest.update(block)
            remaining -= len(block)
        return digest.digest() == f.read(16)


class InsufficientSpaceError(OSError):
    pass


def _check_space(destination, additional_bytes, files=1):
    """Check incremental writes on the actual volume, including staging.

    Existing files already reduce the filesystem's free-space count. Do not
    subtract their size again or assume a replacement can delete them early.
    Allow 64 KiB per entry for allocation rounding and directory metadata.
    """
    if additional_bytes <= 0:
        return
    directory = os.path.abspath(destination)
    while not os.path.isdir(directory):
        directory = os.path.dirname(directory)
    required = additional_bytes + (files + 1) * 65536
    free = shutil.disk_usage(directory).free
    if free < required:
        raise InsufficientSpaceError(f"Insufficient disk space in {directory}: need {_human(required)} additional, "
                      f"{_human(free)} free. Existing downloads and installations are retained.")


def _remaining_download(dest, expected_size):
    if expected_size is None:
        return None
    part = dest + '.part'
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    return max(0, expected_size - have)


def download(url, dest, expected_size=None, sha256=None, retries=5, verify_zim=False):
    """Download with resume support (.part). Prefer curl when available; otherwise use urllib."""
    _require_https(url)
    if ((expected_size is not None or sha256 or verify_zim) and _file_valid(dest, expected_size, sha256)
            and (not verify_zim or _zim_checksum_valid(dest))):
        return dest
    part = dest + ".part"
    if ((expected_size is not None or sha256 or verify_zim)
            and _file_valid(part, expected_size, sha256)
            and (not verify_zim or _zim_checksum_valid(part))):
        os.replace(part, dest)
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    remaining = _remaining_download(dest, expected_size)
    if remaining is not None:
        _check_space(dest, remaining)
        print(f"  Remaining download: {_human(remaining)}")
    part = dest + ".part"
    name = os.path.basename(dest)
    print(f"  ↓ {name}")
    curl = shutil.which("curl")
    ok = False
    if curl and expected_size is not None:
        cmd = [curl, "-L", "--proto", "=https", "--proto-redir", "=https",
               "--connect-timeout", "30", "--speed-time", "60", "--speed-limit", "1",
               "--fail", "--retry", str(retries), "--retry-delay", "3",
               "-C", "-", "-A", USER_AGENT, "-o", part, url]
        for attempt in range(retries):
            _check_space(dest, _remaining_download(dest, expected_size))
            rc = subprocess.call(cmd)
            if rc == 0:
                ok = True
                break
            if rc == 33:  # server does not support resume: restart
                try:
                    os.remove(part)
                except OSError:
                    pass
            time.sleep(3)
    if not ok:
        ok = _download_urllib(url, part, retries)
    if not ok:
        raise RuntimeError("download failed")
    if not _file_valid(part, expected_size):
        raise RuntimeError("download size mismatch (partial file retained for retry)")
    if sha256 and not _file_valid(part, expected_size, sha256):
        os.remove(part)
        raise RuntimeError("sha256 mismatch")
    if verify_zim and not _zim_checksum_valid(part):
        os.remove(part)
        raise RuntimeError("ZIM header or embedded checksum mismatch")
    os.replace(part, dest)
    return dest


def _download_urllib(url, part, retries):
    _require_https(url)
    for attempt in range(retries):
        try:
            have = os.path.getsize(part) if os.path.exists(part) else 0
            headers = {"User-Agent": USER_AGENT}
            if have:
                headers["Range"] = f"bytes={have}-"
            req = urllib.request.Request(url, headers=headers)
            with _HTTPS_OPENER.open(req, timeout=60) as r:
                previous_size = have
                if have and r.status != 206:
                    have = 0
                length = r.headers.get("Content-Length")
                total = int(length) + have if length else None
                if r.status == 206:
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", r.headers.get("Content-Range", ""))
                    if not match:
                        raise RuntimeError("invalid Content-Range")
                    start, end, complete = map(int, match.groups())
                    if start != have or end < start or end + 1 != complete or (length and int(length) != end - start + 1):
                        raise RuntimeError("unexpected Content-Range")
                    total = complete
                mode = "ab" if have else "wb"
                if total is not None:
                    # A 200 response restarts/truncates the existing partial.
                    _check_space(part, max(0, total - previous_size))
                done = have
                last = 0
                with open(part, mode) as f:
                    while True:
                        block = r.read(1 << 20)
                        if not block:
                            break
                        if total is None:
                            _check_space(part, len(block))
                        f.write(block)
                        done += len(block)
                        if time.time() - last > 1:
                            pct = f"{done * 100 / total:5.1f}%" if total else ""
                            sys.stdout.write(f"\r    {_human(done)} {pct}   ")
                            sys.stdout.flush()
                            last = time.time()
                sys.stdout.write("\n")
                if total is not None and done != total:
                    raise RuntimeError("incomplete response")
            return True
        except InsufficientSpaceError:
            raise
        except Exception as e:
            print(f"    attempt {attempt + 1}/{retries} failed: {e}")
            time.sleep(3)
    return False


def _archive_name(name):
    if not name or name.startswith('/') or any(c in name for c in ('\\', ':', '\0')):
        raise ValueError('Invalid archive path: ' + name)
    if '..' in name.split('/'):
        raise ValueError('Archive path traverses parent: ' + name)
    return posixpath.normpath(name)


def _archive_path(destination, name):
    """Reject existing symlinks before touching any destination member."""
    name = _archive_name(name)
    path = os.path.abspath(destination)
    if os.path.islink(path):
        raise ValueError('Archive destination is a symlink')
    for part in name.split('/'):
        path = os.path.join(path, part)
        if os.path.islink(path):
            raise ValueError('Archive path traverses a symlink: ' + name)
    return path


def _archive_write(source, path, mode):
    # Replace rather than truncate: existing hard links must not alter outside files.
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.extract-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'wb') as out:
            shutil.copyfileobj(source, out, length=1024 * 1024)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _archive_link_target(member, members):
    seen = set()
    while member.issym() or member.islnk():
        name = _archive_name(member.name)
        if name in seen:
            raise ValueError('Cyclic archive link: ' + name)
        seen.add(name)
        target = member.linkname
        if not target or target.startswith('/') or any(c in target for c in ('\\', ':', '\0')):
            raise ValueError('Invalid archive link target: ' + target)
        if member.issym():
            target = posixpath.join(posixpath.dirname(name), target)
        target = _archive_name(posixpath.normpath(target))
        if target not in members:
            raise ValueError('Archive link target is missing: ' + target)
        member = members[target]
    return member


def extract(archive, dest, allow_links=True):
    """Validate the whole archive, then extract without version-dependent filters.

    Callers must use a destination that is not concurrently modified by others.
    Upgraders can reject TAR links; preparation preserves safe internal links.
    """
    archive, dest = os.fspath(archive), os.fspath(dest)
    _archive_path(dest, '.')
    os.makedirs(dest, exist_ok=True)
    allowed = _creation_permissions(dest) if os.name != 'nt' else 0o777
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as source:
            members = source.infolist()
            seen = set()
            for member in members:
                name = _archive_name(member.filename)
                _archive_path(dest, name)
                kind = stat.S_IFMT(member.external_attr >> 16)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('Archive links and special files are unsupported')
                if name in seen or (name == '.' and not member.is_dir()):
                    raise ValueError('Duplicate or invalid archive path: ' + name)
                seen.add(name)
            _check_space(dest, sum(m.file_size for m in members), len(members))
            for member in members:
                path = _archive_path(dest, member.filename)
                if member.is_dir():
                    os.makedirs(path, exist_ok=True)
                else:
                    filename = os.path.basename(path)
                    executable = filename in _ZIP_EXECUTABLES or re.fullmatch(r'python3\.\d+', filename)
                    mode = (0o755 if executable else 0o666) & allowed
                    with source.open(member) as stream:
                        _archive_write(stream, path, mode)
        return
    with tarfile.open(archive) as source:
        members = source.getmembers()
        by_name = {}
        for member in members:
            name = _archive_name(member.name)
            _archive_path(dest, name)
            if name in by_name or (name == '.' and not member.isdir()):
                raise ValueError('Duplicate or invalid archive path: ' + name)
            if not (member.isfile() or member.isdir() or
                    (allow_links and (member.issym() or member.islnk()))):
                raise ValueError('Archive links and special files are unsupported')
            by_name[name] = member
        links = [m for m in members if m.issym() or m.islnk()]
        targets = {_archive_name(m.name): _archive_link_target(m, by_name) for m in links}
        for name in by_name:
            parent = posixpath.dirname(name)
            while parent:
                if parent in by_name and not by_name[parent].isdir():
                    raise ValueError('Archive parent is not a directory: ' + parent)
                parent = posixpath.dirname(parent)
        for member in links:
            target = targets[_archive_name(member.name)]
            if not target.isfile() and (member.islnk() or os.name == 'nt'):
                raise ValueError('Archive directory links require manual installation')
        size = sum(m.size for m in members if m.isfile())
        if os.name == 'nt':
            size += sum(m.size for m in targets.values())
        _check_space(dest, size, len(members))
        # Regular files first: forward links are valid and need no gzip rewinds.
        for member in members:
            path = _archive_path(dest, member.name)
            if member.isdir():
                os.makedirs(path, exist_ok=True)
            elif member.isfile():
                with source.extractfile(member) as stream:
                    _archive_write(stream, path, member.mode & 0o777 & allowed)
        for member in links:
            path = _archive_path(dest, member.name)
            target = targets[_archive_name(member.name)]
            target_path = _archive_path(dest, target.name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.name == 'nt':
                # Case-only terminfo aliases already refer to the extracted file.
                if os.path.normcase(path) != os.path.normcase(target_path):
                    with open(target_path, 'rb') as stream:
                        _archive_write(stream, path, target.mode & 0o777 & allowed)
            else:
                if os.path.exists(path):
                    os.remove(path)
                if member.issym():
                    os.symlink(os.path.relpath(target_path, os.path.dirname(path)), path)
                else:
                    os.link(target_path, path)


_ZIP_EXECUTABLES = frozenset({
    "llama-server", "llama-cli", "kiwix-serve", "kiwix-search", "kiwix-manage",
    "pdftotext", "pdfinfo", "python", "python3",
})


def _creation_permissions(destination):
    """Observe the umask via file creation without changing process-global state."""
    with tempfile.TemporaryDirectory(prefix=".permissions-", dir=destination) as folder:
        # The probe directory must remain traversable even if the umask masks x.
        os.chmod(folder, 0o700)
        fd = os.open(os.path.join(folder, "probe"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o777)
        try:
            return stat.S_IMODE(os.fstat(fd).st_mode) & 0o777
        finally:
            os.close(fd)
