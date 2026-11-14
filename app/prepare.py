"""Kit setup (run online once with python emergency.py prepare): download the AI engine, model, Kiwix libraries and portable Python.

Everything goes inside the repository (models/, zim/, runtime/). Copy the whole folder
to a USB drive or disk to use it offline on Windows, Linux and macOS.
"""

import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from .config import launcher_command, ALL_PLATFORMS, CONFIG_DIR, MODELS_DIR, RUNTIME_DIR, ZIM_DIR, load_json, platform_key
from .net import USER_AGENT, get_json, get_text

LLAMA_REPO = "ggml-org/llama.cpp"
PYTHON_REPO = "astral-sh/python-build-standalone"
KIWIX_TOOLS_DIR = "https://download.kiwix.org/release/kiwix-tools/"

# Base builds: CPU on Windows/Linux, Metal-capable on macOS.
LLAMA_ASSETS = {
    "windows-x86_64": ["win-cpu-x64", "win-avx2-x64", "win-x64"],
    "windows-arm64": ["win-cpu-arm64", "win-arm64"],
    "linux-x86_64": ["ubuntu-x64", "ubuntu-cpu-x64", "linux-x64"],
    "linux-arm64": ["ubuntu-arm64", "ubuntu-cpu-arm64", "linux-arm64"],
    "macos-arm64": ["macos-arm64"],
    "macos-x86_64": ["macos-x64"],
}
LLAMA_VULKAN_ASSETS = {
    "windows-x86_64": ["win-vulkan-x64"],
    "windows-arm64": ["win-vulkan-arm64"],
    "linux-x86_64": ["ubuntu-vulkan-x64"],
    "linux-arm64": ["ubuntu-vulkan-arm64"],
}
# Portable Python (python-build-standalone, "install_only").
PYTHON_TRIPLES = {
    "windows-x86_64": "x86_64-pc-windows-msvc",
    "windows-arm64": "aarch64-pc-windows-msvc",
    "linux-x86_64": "x86_64-unknown-linux-gnu",
    "linux-arm64": "aarch64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
    "macos-x86_64": "x86_64-apple-darwin",
}
# kiwix-tools (includes kiwix-serve).
KIWIX_ASSETS = {
    "windows-x86_64": ["win-x86_64", "win-i686"],
    "windows-arm64": ["win-x86_64", "win-i686"],
    "linux-x86_64": ["linux-x86_64"],
    "linux-arm64": ["linux-aarch64", "linux-arm64"],
    "macos-arm64": ["macos-arm64", "macos-x86_64"],
    "macos-x86_64": ["macos-x86_64"],
}

T = {
    "pt": {
        "title": "Preparação do kit — Emergency AI",
        "need_net": "Este passo precisa de internet. Depois disso, tudo funciona offline.",
        "model_q": "Qual modelo de IA baixar?",
        "none": "Nenhum (só busca nos guias, sem IA generativa)",
        "zim_q": "Quais bases offline do Kiwix baixar?",
        "os_q": "Para quais sistemas preparar o kit?",
        "os_this": "Só este computador ({p})",
        "os_all": "Windows + Linux + macOS (kit universal para pendrive)",
        "py_q": "Incluir Python portátil (para computadores sem Python instalado)? [S/n] ",
        "total": "Download estimado: {gb:.1f} GiB. Espaço livre no disco: {free:.1f} GiB.",
        "confirm": "Continuar? [S/n] ",
        "choice": "Escolha [{d}]: ",
        "partial": "Alguns itens falharam (veja acima). Verifique a internet e execute 'python emergency.py prepare --resume': ele retoma de onde parou.",
        "done": "Kit pronto! Execute 'python emergency.py' para usar. Copie a pasta inteira para um pendrive/HD para levar.",
        "skip": "  ↷ já existe, pulando: {f}",
        "fail": "  ✗ falhou: {f} ({e})",
        "manual": "    Baixe manualmente em {u} e coloque em {d}",
        "notfound": "  ✗ não encontrado no catálogo: {n}",
        "cancel": "Cancelado.",
        "yes": ("s", "sim", "y", "yes", ""),
    },
    "en": {
        "title": "Kit setup — Emergency AI",
        "need_net": "This step needs internet. After that, everything works offline.",
        "model_q": "Which AI model to download?",
        "none": "None (guide search only, no generative AI)",
        "zim_q": "Which Kiwix offline libraries to download?",
        "os_q": "Which systems should the kit support?",
        "os_this": "Only this computer ({p})",
        "os_all": "Windows + Linux + macOS (universal USB kit)",
        "py_q": "Include portable Python (for computers without Python)? [Y/n] ",
        "total": "Estimated download: {gb:.1f} GiB. Free disk space: {free:.1f} GiB.",
        "confirm": "Continue? [Y/n] ",
        "choice": "Choose [{d}]: ",
        "partial": "Some items failed (see above). Check your connection and run 'python emergency.py prepare --resume': it resumes where it stopped.",
        "done": "Kit ready! Run 'python emergency.py' to use it. Copy the whole folder to a USB drive to carry it.",
        "skip": "  ↷ already present, skipping: {f}",
        "fail": "  ✗ failed: {f} ({e})",
        "manual": "    Download manually from {u} and put it in {d}",
        "notfound": "  ✗ not found in catalog: {n}",
        "cancel": "Cancelled.",
        "yes": ("y", "yes", "s", "sim", ""),
    },
    "es": {
        "title": "Preparación del kit — Emergency AI",
        "need_net": "Este paso necesita internet. Después, todo funciona sin conexión.",
        "model_q": "¿Qué modelo de IA descargar?",
        "none": "Ninguno (solo búsqueda en las guías, sin IA generativa)",
        "zim_q": "¿Qué bibliotecas offline de Kiwix descargar?",
        "os_q": "¿Para qué sistemas preparar el kit?",
        "os_this": "Solo esta computadora ({p})",
        "os_all": "Windows + Linux + macOS (kit universal para pendrive)",
        "py_q": "¿Incluir Python portátil (para computadoras sin Python)? [S/n] ",
        "total": "Descarga estimada: {gb:.1f} GiB. Espacio libre en disco: {free:.1f} GiB.",
        "confirm": "¿Continuar? [S/n] ",
        "choice": "Elige [{d}]: ",
        "partial": "Algunos elementos fallaron (ver arriba). Revisa la conexión y ejecuta 'python emergency.py prepare --resume': continúa donde se detuvo.",
        "done": "¡Kit listo! Ejecuta 'python emergency.py' para usarlo. Copia toda la carpeta a un pendrive/disco para llevarlo.",
        "skip": "  ↷ ya existe, omitiendo: {f}",
        "fail": "  ✗ falló: {f} ({e})",
        "manual": "    Descárgalo manualmente desde {u} y ponlo en {d}",
        "notfound": "  ✗ no encontrado en el catálogo: {n}",
        "cancel": "Cancelado.",
        "yes": ("s", "si", "sí", "y", "yes", ""),
    },
}


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
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            _check_space(dest, sum(m.file_size for m in z.infolist()), len(z.infolist()))
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            members = t.getmembers()
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
    # ZIP does not preserve executable permissions
    for dirpath, _, files in os.walk(dest):
        for f in files:
            p = os.path.join(dirpath, f)
            if "." not in f or f.endswith((".so", ".dylib")) or ".so." in f:
                try:
                    os.chmod(p, os.stat(p).st_mode | 0o755)
                except OSError:
                    pass


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


def github_latest_assets(repo):
    data = get_json(f"https://api.github.com/repos/{repo}/releases/latest", timeout=30)
    return data.get("tag_name", ""), [(a["name"], a["browser_download_url"], a.get("size")) for a in data.get("assets", [])]


# ---------------------------------------------------------------- components
def _llama_pick(plat, assets, backend="cpu"):
    patterns = LLAMA_VULKAN_ASSETS if backend == "vulkan" else LLAMA_ASSETS
    for key in patterns.get(plat, []):
        rx = re.compile(rf"^llama-.*-bin-{re.escape(key)}\.(zip|tar\.gz)$")
        match = [a for a in assets if rx.match(a[0])]
        if match:
            return match[0]
    return None


def _has_llama_server(folder, plat):
    name = "llama-server.exe" if plat.startswith("windows-") else "llama-server"
    return any(name in files for _, _, files in os.walk(folder))


def _cuda_pick(plat, assets):
    """Require the engine and companion libraries from the same release/version."""
    targets = {"windows-x86_64": "win", "windows-arm64": "win",
               "linux-x86_64": "ubuntu", "linux-arm64": "ubuntu"}
    if plat not in targets:
        return None
    arch = "arm64" if plat.endswith("arm64") else "x64"
    pattern = re.compile(rf"^llama-.*-bin-({targets[plat]}-cuda-(\d+)\.(\d+)-{arch}\.(?:zip|tar\.gz))$")
    pairs = []
    for engine in assets:
        match = pattern.match(engine[0])
        if not match:
            continue
        runtime = next((a for a in assets if a[0].startswith("cudart-llama-")
                        and a[0].endswith("-bin-" + match[1])), None)
        if runtime:
            pairs.append(((int(match[2]), int(match[3])), engine, runtime))
    return max(pairs, key=lambda p: p[0])[1:] if pairs else None


def get_llama(plat, tr, cuda=False):
    try:
        # Always check online, even when an older or unversioned engine is installed.
        releases = get_json(f"https://api.github.com/repos/{LLAMA_REPO}/releases?per_page=10", timeout=30)
        for rel in releases:
            tag = rel.get("tag_name", "")
            assets = [(a["name"], a["browser_download_url"], a.get("size")) for a in rel.get("assets", [])]
            found = _llama_pick(plat, assets)
            if found:
                break
        else:
            raise RuntimeError("asset not found for " + plat)
    except Exception as e:
        print(tr["fail"].format(f=f"llama.cpp ({plat})", e=e))
        return False
    if not _install_llama(plat, tr, tag, found):
        return False
    if plat in LLAMA_VULKAN_ASSETS:
        accelerated = _llama_pick(plat, assets, "vulkan")
        if accelerated:
            if not _install_llama(plat, tr, tag, accelerated, "vulkan"):
                return False
        else:
            print(f"  Vulkan package unavailable for {plat} in {tag}; CPU remains available.")
        if cuda:
            pair = _cuda_pick(plat, assets)
            if not pair:
                print(tr["fail"].format(f=f"CUDA ({plat})", e="matching engine/runtime pair unavailable"))
                return False
            return _install_llama(plat, tr, tag, pair[0], "cuda", pair[1])
    return True


def _install_llama(plat, tr, tag, asset, backend="cpu", companion=None):
    # Sibling folders keep GPU libraries out of the CPU loader's search path.
    folder = plat + ("-" + backend if backend != "cpu" else "")
    dest = os.path.join(RUNTIME_DIR, "llama.cpp", folder)
    label = f"llama.cpp {tag} ({folder})"
    try:
        name, url, size = asset
        release = {"tag": tag, "asset": name}
        if companion:
            release["runtime_asset"] = companion[0]
        installed = load_json(os.path.join(dest, "release.json"), {})
        runtime_files = installed.get("runtime_files", {})
        runtime_ok = not companion or (bool(runtime_files) and all(
            os.path.isfile(os.path.join(dest, path)) and os.path.getsize(os.path.join(dest, path)) == size
            for path, size in runtime_files.items()))
        if {k: v for k, v in installed.items() if k != "runtime_files"} == release and runtime_ok and _has_llama_server(dest, plat):
            print(tr["skip"].format(f=label))
            return True
        archive = os.path.join(RUNTIME_DIR, "_downloads", name)
        download(url, archive, expected_size=size)
        if size is not None and os.path.getsize(archive) != size:
            raise RuntimeError("download size mismatch for " + name)
        runtime_archive = None
        if companion:
            runtime_archive = os.path.join(RUNTIME_DIR, "_downloads", companion[0])
            download(companion[1], runtime_archive, expected_size=companion[2])
            if companion[2] is not None and os.path.getsize(runtime_archive) != companion[2]:
                raise RuntimeError("download size mismatch for " + companion[0])
        parent = os.path.dirname(dest)
        os.makedirs(parent, exist_ok=True)
        # Extract separately so interrupted updates cannot corrupt the working kit.
        staging = tempfile.mkdtemp(prefix=".llama-update-", dir=parent)
        fresh = os.path.join(staging, "new")
        previous = os.path.join(staging, "previous")
        try:
            extract(archive, fresh)
            if not _has_llama_server(fresh, plat):
                raise RuntimeError("archive does not contain llama-server for " + plat)
            if runtime_archive:
                libraries = os.path.join(staging, "libraries")
                extract(runtime_archive, libraries)
                server = "llama-server.exe" if plat.startswith("windows-") else "llama-server"
                bindir = next(d for d, _, files in os.walk(fresh) if server in files)
                runtime_files = {}
                for directory, _, files in os.walk(libraries):
                    for filename in files:
                        # Flatten runtime libraries beside the executable; retain bundled licenses.
                        source = os.path.join(directory, filename)
                        target = os.path.join(bindir, filename)
                        if os.path.exists(target):
                            raise RuntimeError("CUDA companion file collides with engine: " + filename)
                        _check_space(target, os.path.getsize(source))
                        shutil.copy2(source, target)
                        runtime_files[os.path.relpath(target, fresh)] = os.path.getsize(target)
                if not any("cudart" in path.lower() for path in runtime_files):
                    raise RuntimeError("CUDA companion archive lacks runtime libraries")
                release["runtime_files"] = runtime_files
            with open(os.path.join(fresh, "release.json"), "w", encoding="utf-8") as f:
                json.dump(release, f, indent=2)
            had_previous = os.path.exists(dest)
            if had_previous:
                os.replace(dest, previous)
            try:
                os.replace(fresh, dest)
            except OSError:
                if had_previous:
                    os.replace(previous, dest)
                raise
            if had_previous:
                shutil.rmtree(previous)
        finally:
            # If rollback itself fails, retain the backup for recovery.
            if not os.path.exists(previous):
                shutil.rmtree(staging, ignore_errors=True)
        os.remove(archive)
        if runtime_archive:
            os.remove(runtime_archive)
        print(f"  ✓ {label}")
        return True
    except Exception as e:
        print(tr["fail"].format(f=label, e=e))
        print(tr["manual"].format(u=f"https://github.com/{LLAMA_REPO}/releases", d=dest))
        return False


def _python_installed(plat):
    dest = os.path.join(RUNTIME_DIR, "python", plat)
    executable = os.path.join(dest, "python", "python.exe" if plat.startswith("windows-") else "bin/python3")
    return bool(load_json(os.path.join(dest, "installation.json"), {}).get("complete") and os.path.isfile(executable))


def choose_portable_python(platforms, lang):
    messages = {
        "en": ("Reusing installed portable Python: {platforms}. No download for these platforms.",
               "No Python download is needed for the selected platforms.",
               "Download or repair portable Python for {platforms}? [Y/n] "),
        "pt": ("Reutilizando o Python portátil instalado: {platforms}. Sem download para esses sistemas.",
               "Não é necessário baixar Python para os sistemas selecionados.",
               "Baixar ou reparar Python portátil para {platforms}? [S/n] "),
        "es": ("Reutilizando Python portátil instalado: {platforms}. Sin descarga para estos sistemas.",
               "No es necesario descargar Python para los sistemas seleccionados.",
               "¿Descargar o reparar Python portátil para {platforms}? [S/n] "),
    }
    reuse, complete, question = messages.get(lang, messages["en"])
    installed = [plat for plat in platforms if _python_installed(plat)]
    missing = [plat for plat in platforms if plat not in installed]
    if installed:
        print(reuse.format(platforms=", ".join(installed)))
    if not missing:
        print(complete)
        return True
    return _yes(question.format(platforms=", ".join(missing)), T.get(lang, T["en"]))


def get_python(plat, tr):
    dest = os.path.join(RUNTIME_DIR, "python", plat)
    executable = os.path.join(dest, "python", "python.exe" if plat.startswith("windows-") else "bin/python3")
    if _python_installed(plat):
        print(tr["skip"].format(f=f"Python ({plat})"))
        return True
    triple = PYTHON_TRIPLES[plat]
    try:
        tag, assets = github_latest_assets(PYTHON_REPO)
        rx = re.compile(rf"^cpython-3\.12\.\d+\+\d+-{re.escape(triple)}-install_only\.tar\.gz$")
        match = [a for a in assets if rx.match(a[0])]
        if not match:
            rx = re.compile(rf"^cpython-3\.1[1-3]\.\d+\+\d+-{re.escape(triple)}-install_only\.tar\.gz$")
            match = [a for a in assets if rx.match(a[0])]
        if not match:
            raise RuntimeError("asset not found")
        name, url, size = sorted(match)[-1]
        archive = os.path.join(RUNTIME_DIR, "_downloads", name)
        download(url, archive, expected_size=size)
        parent = os.path.dirname(dest)
        os.makedirs(parent, exist_ok=True)
        staging = tempfile.mkdtemp(prefix=".python-install-", dir=parent)
        fresh = os.path.join(staging, "new")
        previous = os.path.join(staging, "previous")
        try:
            extract(archive, fresh)
            relative_exe = os.path.relpath(executable, dest)
            if not os.path.isfile(os.path.join(fresh, relative_exe)):
                raise RuntimeError("archive does not contain Python for " + plat)
            with open(os.path.join(fresh, "installation.json"), "w", encoding="utf-8") as f:
                json.dump({"complete": True, "asset": name}, f)
            had_previous = os.path.exists(dest)
            if had_previous:
                os.replace(dest, previous)
            try:
                os.replace(fresh, dest)
            except OSError:
                if had_previous:
                    os.replace(previous, dest)
                raise
            if had_previous:
                shutil.rmtree(previous)
        finally:
            if not os.path.exists(previous):
                shutil.rmtree(staging, ignore_errors=True)
        os.remove(archive)
        print(f"  ✓ Portable Python ({plat})")
        return True
    except Exception as e:
        print(tr["fail"].format(f=f"Python ({plat})", e=e))
        print(tr["manual"].format(u=f"https://github.com/{PYTHON_REPO}/releases", d=dest))
        return False


def get_kiwix_tools(plat, tr):
    dest = os.path.join(RUNTIME_DIR, "kiwix-tools", plat)
    if load_json(os.path.join(dest, "installation.json"), {}).get("complete") and any(f in ("kiwix-serve", "kiwix-serve.exe") for _, _, fs in os.walk(dest) for f in fs):
        print(tr["skip"].format(f=f"kiwix-tools ({plat})"))
        return True
    try:
        listing = get_text(KIWIX_TOOLS_DIR, timeout=30)
        files = set(re.findall(r'href="(kiwix-tools_[^"]+\.(?:zip|tar\.gz))"', listing))
        for key in KIWIX_ASSETS[plat]:
            rx = re.compile(rf"^kiwix-tools_{re.escape(key)}-(\d+(?:\.\d+)*)\.(zip|tar\.gz)$")
            versions = []
            for f in files:
                m = rx.match(f)
                if m:
                    versions.append((tuple(int(x) for x in m.group(1).split(".")), f))
            if versions:
                fname = sorted(versions)[-1][1]
                archive = os.path.join(RUNTIME_DIR, "_downloads", fname)
                download(KIWIX_TOOLS_DIR + fname, archive)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".kiwix-install-", dir=os.path.dirname(dest)) as staging:
                    fresh = os.path.join(staging, "new")
                    previous = os.path.join(staging, "previous")
                    extract(archive, fresh)
                    binary = "kiwix-serve.exe" if plat.startswith("windows-") else "kiwix-serve"
                    if not any(binary in files for _, _, files in os.walk(fresh)):
                        raise RuntimeError("archive does not contain " + binary)
                    with open(os.path.join(fresh, "installation.json"), "w") as marker:
                        json.dump({"complete": True}, marker)
                    had_previous = os.path.exists(dest)
                    if had_previous:
                        os.replace(dest, previous)
                    try:
                        os.replace(fresh, dest)
                    except OSError:
                        if had_previous:
                            os.replace(previous, dest)
                        raise
                os.remove(archive)
                print(f"  ✓ kiwix-tools ({plat}): {fname}")
                return True
        raise RuntimeError("asset not found")
    except Exception as e:
        print(tr["fail"].format(f=f"kiwix-tools ({plat})", e=e))
        print(tr["manual"].format(u=KIWIX_TOOLS_DIR, d=dest))
        return False


def get_model(model, tr):
    dest = os.path.join(MODELS_DIR, model["file"])
    try:
        download(model["url"], dest, expected_size=model.get("size_bytes"), sha256=model.get("sha256"))
        print(f"  ✓ {model['name']}")
        return True
    except Exception as e:
        print(tr["fail"].format(f=model["file"], e=e))
        print(tr["manual"].format(u=model["url"], d=MODELS_DIR))
        return False


def catalog_lookup(catalog_url, name=None, query=None, lang=None, count=1):
    """Query the Kiwix OPDS catalog. Return [{name,title,url,size,lang,summary}]."""
    params = {"count": count}
    if name:
        params["name"] = name
    if query:
        params["q"] = query
    if lang:
        params["lang"] = lang
    xml = get_text(catalog_url + "?" + urllib.parse.urlencode(params), timeout=30)
    root = ET.fromstring(xml)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        item = {
            "name": e.findtext("a:name", "", ns),
            "title": e.findtext("a:title", "", ns),
            "lang": e.findtext("a:language", "", ns),
            "summary": e.findtext("a:summary", "", ns),
            "url": None,
            "size": None,
        }
        for link in e.findall("a:link", ns):
            if link.get("type") == "application/x-zim":
                href = link.get("href", "")
                item["url"] = href[:-6] if href.endswith(".meta4") else href
                item["meta4"] = href if href.endswith(".meta4") else None
                try:
                    item["size"] = int(link.get("length") or 0) or None
                except ValueError:
                    pass
        out.append(item)
    return out


def _meta4_integrity(meta4_url):
    root = ET.fromstring(get_text(meta4_url, timeout=30))
    ns = {"m": "urn:ietf:params:xml:ns:metalink"}
    file = root.find("m:file", ns)
    size = int(file.findtext("m:size", "0", ns)) if file is not None else 0
    digest = file.findtext("m:hash[@type='sha-256']", "", ns) if file is not None else ""
    if size <= 0 or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise RuntimeError("missing size or SHA-256 in metalink")
    return size, digest


def resolve_zim(entry, catalog_url):
    found = catalog_lookup(catalog_url, name=entry["name"], count=100)
    prefix = entry["name"] + ("_" + entry["variant"] if entry.get("variant") else "") + "_"
    candidates = [item for item in found if item.get("url") and
                  os.path.basename(urllib.parse.urlparse(item["url"]).path).startswith(prefix)]
    # ISO release dates in the filenames sort chronologically within a variant.
    return max(candidates, key=lambda item: item["url"], default=None)


def get_zim(entry, catalog_url, tr):
    try:
        item = resolve_zim(entry, catalog_url)
    except Exception as e:
        print(tr["fail"].format(f=entry["name"], e=e))
        return False
    if not item:
        print(tr["notfound"].format(n=entry["name"]))
        return False
    fname = os.path.basename(urllib.parse.urlparse(item["url"]).path)
    dest = os.path.join(ZIM_DIR, fname)
    try:
        # OPDS lengths are rounded; metalink supplies the exact byte count.
        size, sha = _meta4_integrity(item["meta4"]) if item.get("meta4") else (item.get("size"), None)
        download(item["url"], dest, expected_size=size, sha256=sha)
        # The downloader verifies and atomically activates the new file first.
        prefix = entry["name"] + ("_" + entry["variant"] if entry.get("variant") else "") + "_"
        for old in os.listdir(ZIM_DIR):
            if old.startswith(prefix) and old.endswith(".zim") and old != fname:
                print(f"  ↻ replacing {old}")
                os.remove(os.path.join(ZIM_DIR, old))
        print(f"  ✓ {item['title']} ({_human(os.path.getsize(dest))})")
        return True
    except Exception as e:
        print(tr["fail"].format(f=fname, e=e))
        return False


def get_archive(entry, tr):
    """Install a fixed historical edition without removing other editions."""
    filename = os.path.basename(urllib.parse.urlsplit(entry["url"]).path)
    print(f"  [ARCHIVED {entry['snapshot']}] {entry['desc']}")
    print("  " + entry["note"])
    try:
        dest = os.path.join(ZIM_DIR, filename)
        download(entry["url"], dest, expected_size=entry["size_bytes"], verify_zim=True)
        print(f"  Ready: {filename}")
        return True
    except Exception as e:
        print(tr["fail"].format(f=filename, e=e))
        return False


# ---------------------------------------------------------------- interface
def system_ram_bytes():
    """Total physical memory visible to this OS; None if detection fails."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
                    (name, ctypes.c_uint64) for name in (
                        "total_physical", "available_physical", "total_page_file",
                        "available_page_file", "total_virtual", "available_virtual", "extended")]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            total = status.total_physical
        elif sys.platform == "darwin":
            total = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=5,
                stderr=subprocess.DEVNULL).strip())
        elif sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="ascii") as stream:
                total = next(int(line.split()[1]) * 1024 for line in stream
                             if line.startswith("MemTotal:"))
        else:
            return None
        return total if total > 0 else None
    except (OSError, ValueError, IndexError, StopIteration, AttributeError, subprocess.SubprocessError):
        return None


def _model_options(models, lang):
    labels = {
        "en": ("System RAM: {ram:.1f} GiB", "System RAM: could not detect",
               "{ram} GB RAM recommended", "meets RAM recommendation", "below RAM recommendation",
               "Estimates for this computer, not a guarantee: context size and other apps also use RAM. You can still select any model."),
        "pt": ("RAM do sistema: {ram:.1f} GiB", "RAM do sistema: não foi possível detectar",
               "{ram} GB de RAM recomendados", "atende à recomendação de RAM", "abaixo da recomendação de RAM",
               "Estimativas para este computador, sem garantia: o contexto e outros aplicativos também usam RAM. Você pode escolher qualquer modelo."),
        "es": ("RAM del sistema: {ram:.1f} GiB", "RAM del sistema: no se pudo detectar",
               "{ram} GB de RAM recomendados", "cumple la recomendación de RAM", "por debajo de la recomendación de RAM",
               "Estimaciones para esta computadora, sin garantía: el contexto y otras aplicaciones también usan RAM. Puedes elegir cualquier modelo."),
    }
    detected, unknown, recommendation, meets, below, note = labels.get(lang, labels["en"])
    ram = system_ram_bytes()
    print("\n" + (detected.format(ram=ram / 1024**3) if ram else unknown))
    print(note)
    options = []
    for model in models:
        memory = recommendation.format(ram=model["ram_gb"])
        if ram:
            memory += " — " + (meets if ram >= model["ram_gb"] * 1024**3 else below)
        options.append((model["id"], f"{model['name']} — {model['size_gb']} GB — {memory} — "
                        + model["desc"].get(lang, model["desc"]["en"])))
    return options


def _ask(prompt, options, default, tr):
    print("\n" + prompt)
    for i, (key, label) in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        try:
            raw = input(tr["choice"].format(d=default)).strip()
        except EOFError:
            raise ValueError("Setup cancelled: input closed. Use --yes for unattended setup.")
        if not raw:
            raw = str(default)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        for key, _ in options:
            if raw == key:
                return key


def _yes(prompt, tr):
    try:
        return input(prompt).strip().lower() in tr["yes"]
    except EOFError:
        raise ValueError("Setup cancelled: input closed. Use --yes for unattended setup.")


def nvidia_available():
    """Only controls the download offer; the CUDA engine verifies compatibility at launch."""
    binary = shutil.which("nvidia-smi")
    if not binary:
        return False
    try:
        result = subprocess.run([binary, "--query-gpu=name", "--format=csv,noheader"],
                                capture_output=True, text=True, timeout=5,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        return result.returncode == 0 and bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def choose_cuda(lang):
    if not nvidia_available():
        return False
    prompts = {
        "en": "NVIDIA GPU detected. Include optional CUDA acceleration (roughly 0.6–0.8 GB download; compatible driver required)? [Y/n] ",
        "pt": "GPU NVIDIA detectada. Incluir aceleração CUDA opcional (download de cerca de 0,6–0,8 GB; requer driver compatível)? [S/n] ",
        "es": "GPU NVIDIA detectada. ¿Incluir aceleración CUDA opcional (descarga de unos 0,6–0,8 GB; requiere controlador compatible)? [S/n] ",
    }
    return _yes(prompts.get(lang, prompts["en"]), T.get(lang, T["en"]))


def run(lang="en", model=None, zims=None, oses=None, python=None, yes=False, search=None, skip_tools=False,
        archives=None, resume=False, cuda=None):
    from .startup import load_selection, save_selection
    if resume:
        saved = load_selection(RUNTIME_DIR)
        if not saved:
            raise ValueError(f"No saved setup choices. Run '{launcher_command()} prepare' first.")
        model = model if model is not None else saved.get("model", "none")
        zims = zims if zims is not None else saved.get("zims", "none")
        archives = archives if archives is not None else saved.get("archives", "none")
        python = python if python is not None else saved.get("python", False)
        cuda = cuda if cuda is not None else saved.get("cuda", False)
        oses = oses or ",".join(saved.get("platforms", [platform_key()]))
    tr = dict(T.get(lang, T["en"]))
    launcher = r".\run.bat" if os.name == "nt" else "./run.sh"
    for key in ("done", "partial"):
        tr[key] = tr[key].replace("python emergency.py", launcher)
    models_cfg = load_json(os.path.join(CONFIG_DIR, "models.json"), {})
    zims_cfg = load_json(os.path.join(CONFIG_DIR, "zims.json"), {})
    catalog = zims_cfg.get("catalog_url", "https://library.kiwix.org/catalog/v2/entries")
    here = platform_key()

    if search:
        results = catalog_lookup(catalog, query=search, count=40)
        for r in results:
            size = _human(r["size"]) if r["size"] else "?"
            print(f"- {r['name']:45s} {r['lang']:8s} {size:>10s}  {r['title']}")
        print("\nAdd the desired 'name' to config/zims.json to download it.")
        return 0

    print("=" * 64)
    print(tr["title"])
    print("=" * 64)
    print(tr["need_net"])

    interactive = model is None and zims is None and oses is None and archives is None and not yes
    advanced = False
    if interactive:
        labels = {
            "en": ("Setup options", "Recommended choices", "Advanced models and archived libraries"),
            "pt": ("Opções de configuração", "Opções recomendadas", "Modelos avançados e bibliotecas arquivadas"),
            "es": ("Opciones de configuración", "Opciones recomendadas", "Modelos avanzados y bibliotecas archivadas"),
        }
        title, basic, extra = labels.get(lang, labels["en"])
        advanced = _ask(title, [("recommended", basic), ("advanced", extra)], 1, tr) == "advanced"

    # Model
    if model is None:
        if interactive:
            opts = _model_options([m for m in models_cfg["models"]
                    if advanced or m["id"] in models_cfg.get("recommendations", {}).values()], lang)
            opts.append(("none", tr["none"]))
            default = 1 + [o[0] for o in opts].index(models_cfg.get("default", opts[0][0]))
            model = _ask(tr["model_q"], opts, default, tr)
        else:
            model = models_cfg.get("default")
    chosen_model = next((m for m in models_cfg["models"] if m["id"] == model), None)
    if model != "none" and chosen_model is None:
        raise ValueError("Unknown model: " + str(model))

    # ZIMs
    if zims is None:
        if interactive:
            opts = [(k, f"{k}: {v}") for k, v in zims_cfg["profiles"].items()]
            opts.append(("none", tr["none"].split("(")[0].strip()))
            zims = _ask(tr["zim_q"], opts, 2, tr)
        else:
            zims = "minimal"
    chosen_zims = [z for z in zims_cfg["zims"] if zims in z.get("profiles", [])] if zims != "none" else []
    if zims != "none" and (zims not in zims_cfg["profiles"] or not chosen_zims):
        raise ValueError("Unknown or empty ZIM profile: " + str(zims))

    # Archived snapshots are always opt-in, including with --yes and --zims full.
    archive_entries = zims_cfg.get("archives", [])
    if archives is None:
        if interactive and advanced and archive_entries:
            opts = [("none", "None (recommended)")]
            opts += [(a["id"], f"[ARCHIVED {a['snapshot']}] {a['desc']} ({a['size_gb']:.1f} GiB)")
                     for a in archive_entries]
            opts.append(("all", f"All archived snapshots ({sum(a['size_gb'] for a in archive_entries):.1f} GiB)"))
            archives = _ask("Optional archived libraries (may be outdated; WikEM is not current clinical guidance):",
                            opts, 1, tr)
        else:
            archives = "none"
    archive_ids = [] if archives == "none" else ([a["id"] for a in archive_entries] if archives == "all"
                                               else [a.strip() for a in archives.split(",")])
    if any(a not in {entry["id"] for entry in archive_entries} for a in archive_ids):
        raise ValueError("Unknown archive selection: " + str(archives))
    chosen_archives = [a for a in archive_entries if a["id"] in archive_ids]

    # Systems
    if oses is None:
        if interactive:
            oses = _ask(tr["os_q"], [("this", tr["os_this"].format(p=here)), ("all", tr["os_all"])], 1, tr)
        else:
            oses = "this"
    platforms = list(ALL_PLATFORMS) if oses == "all" else [here] if oses == "this" else oses.split(",")
    if any(plat not in ALL_PLATFORMS for plat in platforms):
        raise ValueError("Unsupported platform selection: " + str(oses))
    platforms = list(dict.fromkeys(platforms))

    # Portable Python
    if python is None:
        python = choose_portable_python(platforms, lang) if interactive else (oses == "all")
    if cuda is None:
        cuda = (choose_cuda(lang) if interactive and chosen_model and not skip_tools
                and any(p in LLAMA_VULKAN_ASSETS for p in platforms) else False)

    est = ((chosen_model.get("size_bytes", chosen_model["size_gb"] * 10**9) / 1024**3)
           if chosen_model else 0) + sum(z.get("size_gb", 0) for z in chosen_zims)
    est += sum(a["size_bytes"] for a in chosen_archives) / 1024 ** 3
    print(f"\nSelected model/library data: approximately {est:.1f} GiB before reusing existing files.")
    print("Remaining download bytes and extraction space are checked on each component's destination drive.")
    if interactive and not _yes(tr["confirm"], tr):
        print(tr["cancel"])
        return 1

    results = []

    # Save intent before any network operation so interrupted setup is resumable.
    save_selection({"model": model, "zims": zims, "python": bool(python), "cuda": bool(cuda),
                    "archives": ",".join(a["id"] for a in chosen_archives) or "none", "platforms": platforms}, RUNTIME_DIR)

    def record(name, operation, *args):
        results.append({"name": name, "ok": bool(operation(*args))})

    if not skip_tools:
        for plat in platforms:
            print(f"\n[{plat}]")
            if chosen_model:
                record("llama.cpp/" + plat, get_llama, plat, tr, bool(cuda))
            if chosen_zims or chosen_archives:
                record("kiwix-tools/" + plat, get_kiwix_tools, plat, tr)
            if python:
                record("python/" + plat, get_python, plat, tr)
    if chosen_model:
        print("\n[model]")
        record("model/" + chosen_model["file"], get_model, chosen_model, tr)
    if chosen_zims:
        print("\n[Kiwix ZIM]")
        os.makedirs(ZIM_DIR, exist_ok=True)
        for z in chosen_zims:
            record("zim/" + z["name"], get_zim, z, catalog, tr)
    if chosen_archives:
        print("\n[Archived Kiwix ZIM snapshots - may be outdated]")
        os.makedirs(ZIM_DIR, exist_ok=True)
        for entry in chosen_archives:
            record(f"archive/{entry['id']}/{entry['snapshot']}", get_archive, entry, tr)

    print("\n" + "=" * 64)
    ok = sum(1 for r in results if r["ok"])
    print(f"{ok}/{len(results)} ✓")
    if ok < len(results):
        print(tr["partial"])
    else:
        print(tr["done"])
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    manifest = os.path.join(RUNTIME_DIR, "kit-info.json")
    with open(manifest + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"prepared": time.strftime("%Y-%m-%d %H:%M"), "platforms": platforms,
                   "model": chosen_model["file"] if chosen_model else None,
                   "zim_profile": zims,
                   "archives": [{"id": a["id"], "snapshot": a["snapshot"], "url": a["url"]} for a in chosen_archives],
                   "ready": ok == len(results), "components": results}, f, indent=2)
    os.replace(manifest + ".tmp", manifest)
    return 0 if ok == len(results) else 1
