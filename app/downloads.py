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
import urllib.request
import zipfile

from .net import USER_AGENT

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
        cmd = [curl, "-L", "--fail", "--retry", str(retries), "--retry-delay", "3",
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
    for attempt in range(retries):
        try:
            have = os.path.getsize(part) if os.path.exists(part) else 0
            headers = {"User-Agent": USER_AGENT}
            if have:
                headers["Range"] = f"bytes={have}-"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
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


def extract(archive, dest):
    os.makedirs(dest, exist_ok=True)
    zip_archive = archive.endswith(".zip")
    if zip_archive:
        with zipfile.ZipFile(archive) as z:
            _check_space(dest, sum(m.file_size for m in z.infolist()), len(z.infolist()))
            z.extractall(dest)
            permission_files = [m.filename for m in z.infolist() if not m.is_dir()
                                and not stat.S_ISLNK(m.external_attr >> 16)]
    else:
        with tarfile.open(archive) as t:
            members = t.getmembers()
            permission_files = [m.name for m in members if m.isfile()]
            # Linux Python includes case-only terminfo aliases. On Windows these
            # symlinks can point back to themselves; copy their archived contents
            # instead, also avoiding the need for Windows symlink privileges.
            links = [m for m in members if m.issym() or m.islnk()] if os.name == "nt" else []
            ordinary = [m for m in members if not (m.issym() or m.islnk())] if links else members
            sizes = {os.path.normcase(os.path.normpath(m.name)): m.size for m in members if m.isfile()}
            for member in links:
                target = _tar_link_target(t, member)
                sizes[os.path.normcase(os.path.normpath(member.name))] = target.size
            _check_space(dest, sum(sizes.values()), len(members))
            try:
                t.extractall(dest, members=ordinary, filter="data")
            except TypeError:
                t.extractall(dest, members=ordinary)
            for member in links:
                if hasattr(tarfile, "data_filter"):
                    tarfile.data_filter(member, dest)
                path = os.path.realpath(os.path.join(dest, member.name))
                base = os.path.realpath(dest)
                if os.path.commonpath([base, path]) != base:
                    raise ValueError("Archive link escapes destination: " + member.name)
                # Resolve using case-sensitive archive names. All ordinary files
                # are already extracted, so copying avoids repeatedly seeking
                # backwards through a large gzip archive for each alias.
                target = _tar_link_target(t, member)
                source = os.path.realpath(os.path.join(dest, target.name))
                if os.path.commonpath([base, source]) != base:
                    raise ValueError("Archive link target escapes destination: " + member.name)
                if os.path.normcase(source) != os.path.normcase(path):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    shutil.copy2(source, path)
    if os.name != "nt":
        _restore_permissions(dest, permission_files, zip_archive)


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


def _restore_permissions(destination, members, zip_archive):
    allowed = _creation_permissions(destination)
    base = os.path.realpath(destination)
    for name in members:
        path = os.path.abspath(os.path.join(base, name))
        # Skip links in any path component, not just the final filename.
        if os.path.commonpath([base, path]) != base or os.path.realpath(path) != path:
            continue
        if not stat.S_ISREG(os.lstat(path).st_mode):
            continue
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            mode = stat.S_IMODE(os.fstat(fd).st_mode) & 0o777
            filename = os.path.basename(path)
            if zip_archive and (filename in _ZIP_EXECUTABLES or re.fullmatch(r"python3\.\d+", filename)):
                mode = 0o755
            os.fchmod(fd, mode & allowed)
        finally:
            os.close(fd)


def _tar_link_target(archive, member):
    seen = set()
    while member.issym() or member.islnk():
        if member.name in seen:
            raise ValueError("Cyclic archive link: " + member.name)
        seen.add(member.name)
        name = member.linkname
        if member.issym():
            name = posixpath.join(posixpath.dirname(member.name), name)
        member = archive.getmember(posixpath.normpath(name))
    return member


