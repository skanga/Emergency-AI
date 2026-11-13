"""Kit preparer (run online once): download the AI engine, model, Kiwix libraries and portable Python.

Everything goes inside the repository (models/, zim/, runtime/). Copy the whole folder
to a USB drive or disk to use it offline on Windows, Linux and macOS.
"""

import hashlib
import json
import os
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

from .config import ALL_PLATFORMS, CONFIG_DIR, MODELS_DIR, RUNTIME_DIR, ZIM_DIR, load_json, platform_key
from .net import USER_AGENT, get_json, get_text

LLAMA_REPO = "ggml-org/llama.cpp"
PYTHON_REPO = "astral-sh/python-build-standalone"
KIWIX_TOOLS_DIR = "https://download.kiwix.org/release/kiwix-tools/"

# Filename patterns for prebuilt llama.cpp binaries (CPU-only builds).
LLAMA_ASSETS = {
    "windows-x86_64": ["win-cpu-x64", "win-avx2-x64", "win-x64"],
    "windows-arm64": ["win-cpu-arm64", "win-arm64"],
    "linux-x86_64": ["ubuntu-x64", "ubuntu-cpu-x64", "linux-x64"],
    "linux-arm64": ["ubuntu-arm64", "ubuntu-cpu-arm64", "linux-arm64"],
    "macos-arm64": ["macos-arm64"],
    "macos-x86_64": ["macos-x64"],
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
        "title": "Preparador do kit — Emergency AI",
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
        "partial": "Alguns itens falharam (veja acima). Verifique a internet e rode o preparador de novo: ele retoma de onde parou.",
        "done": "Kit pronto! Rode 'start' para usar. Copie a pasta inteira para um pendrive/HD para levar.",
        "skip": "  ↷ já existe, pulando: {f}",
        "fail": "  ✗ falhou: {f} ({e})",
        "manual": "    Baixe manualmente em {u} e coloque em {d}",
        "notfound": "  ✗ não encontrado no catálogo: {n}",
        "cancel": "Cancelado.",
        "yes": ("s", "sim", "y", "yes", ""),
    },
    "en": {
        "title": "Kit preparer — Emergency AI",
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
        "partial": "Some items failed (see above). Check your connection and run the preparer again: it resumes where it stopped.",
        "done": "Kit ready! Run 'start' to use it. Copy the whole folder to a USB drive to carry it.",
        "skip": "  ↷ already present, skipping: {f}",
        "fail": "  ✗ failed: {f} ({e})",
        "manual": "    Download manually from {u} and put it in {d}",
        "notfound": "  ✗ not found in catalog: {n}",
        "cancel": "Cancelled.",
        "yes": ("y", "yes", "s", "sim", ""),
    },
    "es": {
        "title": "Preparador del kit — Emergency AI",
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
        "partial": "Algunos elementos fallaron (ver arriba). Revisa la conexión y ejecuta el preparador de nuevo: continúa donde se detuvo.",
        "done": "¡Kit listo! Ejecuta 'start' para usarlo. Copia toda la carpeta a un pendrive/disco para llevarlo.",
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


def download(url, dest, expected_size=None, sha256=None, retries=5, verify_zim=False):
    """Download with resume support (.part). Prefer curl when available; otherwise use urllib."""
    if ((expected_size is not None or sha256 or verify_zim) and _file_valid(dest, expected_size, sha256)
            and (not verify_zim or _zim_checksum_valid(dest))):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    name = os.path.basename(dest)
    print(f"  ↓ {name}")
    curl = shutil.which("curl")
    ok = False
    if curl:
        cmd = [curl, "-L", "--fail", "--retry", str(retries), "--retry-delay", "3",
               "-C", "-", "-A", USER_AGENT, "-o", part, url]
        for attempt in range(retries):
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
                done = have
                last = 0
                with open(part, mode) as f:
                    while True:
                        block = r.read(1 << 20)
                        if not block:
                            break
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
        except Exception as e:
            print(f"    attempt {attempt + 1}/{retries} failed: {e}")
            time.sleep(3)
    return False


def extract(archive, dest):
    os.makedirs(dest, exist_ok=True)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            try:
                t.extractall(dest, filter="data")
            except TypeError:
                t.extractall(dest)
    # ZIP does not preserve executable permissions
    for dirpath, _, files in os.walk(dest):
        for f in files:
            p = os.path.join(dirpath, f)
            if "." not in f or f.endswith((".so", ".dylib")) or ".so." in f:
                try:
                    os.chmod(p, os.stat(p).st_mode | 0o755)
                except OSError:
                    pass


def github_latest_assets(repo):
    data = get_json(f"https://api.github.com/repos/{repo}/releases/latest", timeout=30)
    return data.get("tag_name", ""), [(a["name"], a["browser_download_url"], a.get("size")) for a in data.get("assets", [])]


# ---------------------------------------------------------------- components
def _llama_pick(plat, assets):
    for key in LLAMA_ASSETS[plat]:
        rx = re.compile(rf"^llama-.*-bin-{re.escape(key)}\.(zip|tar\.gz)$")
        match = [a for a in assets if rx.match(a[0])]
        if match:
            return match[0]
    return None


def _has_llama_server(folder, plat):
    name = "llama-server.exe" if plat.startswith("windows-") else "llama-server"
    return any(name in files for _, _, files in os.walk(folder))


def get_llama(plat, tr):
    dest = os.path.join(RUNTIME_DIR, "llama.cpp", plat)
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
        name, url, size = found
        release = {"tag": tag, "asset": name}
        installed = load_json(os.path.join(dest, "release.json"), {})
        if installed == release and _has_llama_server(dest, plat):
            print(tr["skip"].format(f=f"llama.cpp {tag} ({plat})"))
            return True
        archive = os.path.join(RUNTIME_DIR, "_downloads", name)
        download(url, archive, expected_size=size)
        if size is not None and os.path.getsize(archive) != size:
            raise RuntimeError("download size mismatch for " + name)
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
        print(f"  ✓ llama.cpp {tag} ({plat})")
        return True
    except Exception as e:
        print(tr["fail"].format(f=f"llama.cpp ({plat})", e=e))
        print(tr["manual"].format(u=f"https://github.com/{LLAMA_REPO}/releases", d=dest))
        return False


def get_python(plat, tr):
    dest = os.path.join(RUNTIME_DIR, "python", plat)
    if os.path.isdir(os.path.join(dest, "python")):
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
        extract(archive, dest)
        os.remove(archive)
        print(f"  ✓ Portable Python ({plat})")
        return True
    except Exception as e:
        print(tr["fail"].format(f=f"Python ({plat})", e=e))
        print(tr["manual"].format(u=f"https://github.com/{PYTHON_REPO}/releases", d=dest))
        return False


def get_kiwix_tools(plat, tr):
    dest = os.path.join(RUNTIME_DIR, "kiwix-tools", plat)
    if os.path.isdir(dest) and any(f.startswith("kiwix-serve") for _, _, fs in os.walk(dest) for f in fs):
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
                extract(archive, dest)
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
def _ask(prompt, options, default, tr):
    print("\n" + prompt)
    for i, (key, label) in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        try:
            raw = input(tr["choice"].format(d=default)).strip()
        except EOFError:
            raw = ""
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
        return True


def run(lang="en", model=None, zims=None, oses=None, python=None, yes=False, search=None, skip_tools=False,
        archives=None, resume=False):
    from .startup import load_selection, save_selection
    if resume:
        saved = load_selection(RUNTIME_DIR)
        if not saved:
            raise ValueError("No saved setup choices. Run 'python emergency.py prepare' first.")
        model = model if model is not None else saved.get("model", "none")
        zims = zims if zims is not None else saved.get("zims", "none")
        archives = archives if archives is not None else saved.get("archives", "none")
        python = python if python is not None else saved.get("python", False)
        oses = oses or "this"
    tr = T.get(lang, T["en"])
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

    # Model
    if model is None:
        if interactive:
            opts = [(m["id"], f"{m['name']} — {m['size_gb']} GB — {m['desc'].get(lang, m['desc']['en'])}")
                    for m in models_cfg["models"]]
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
        if interactive and archive_entries:
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
            oses = _ask(tr["os_q"], [("this", tr["os_this"].format(p=here)), ("all", tr["os_all"])], 2, tr)
        else:
            oses = "this"
    platforms = list(ALL_PLATFORMS) if oses == "all" else [here] if oses == "this" else oses.split(",")
    if any(plat not in ALL_PLATFORMS for plat in platforms):
        raise ValueError("Unsupported platform selection: " + str(oses))
    platforms = list(dict.fromkeys(platforms))

    # Portable Python
    if python is None:
        python = _yes(tr["py_q"], tr) if interactive else (oses == "all")

    est = (chosen_model["size_gb"] if chosen_model else 0) + sum(z.get("size_gb", 0) for z in chosen_zims)
    est += sum(a["size_bytes"] for a in chosen_archives) / 1024 ** 3
    est += 0.06 * len(platforms) * (2 if python else 1) + 0.02 * len(platforms)
    free = shutil.disk_usage(os.path.dirname(MODELS_DIR)).free / 1024 ** 3
    print("\n" + tr["total"].format(gb=est, free=free))
    if interactive and not _yes(tr["confirm"], tr):
        print(tr["cancel"])
        return 1

    results = []

    # Save intent before any network operation so interrupted setup is resumable.
    save_selection({"model": model, "zims": zims, "python": bool(python),
                    "archives": ",".join(a["id"] for a in chosen_archives) or "none"}, RUNTIME_DIR)

    def record(name, operation, *args):
        results.append({"name": name, "ok": bool(operation(*args))})

    if not skip_tools:
        for plat in platforms:
            print(f"\n[{plat}]")
            if chosen_model:
                record("llama.cpp/" + plat, get_llama, plat, tr)
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
