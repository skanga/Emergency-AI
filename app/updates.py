"""Read-only inventory and bounded, immutable update discovery (standard library only)."""
import copy
from concurrent.futures import Future
import datetime
import json
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import platform_key

OFFICIAL_REPO = 'skanga/Emergency-AI'
MAX_METADATA = 8 * 1024 * 1024


def _read(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _text(url, timeout):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Metadata requires HTTPS')
    request = urllib.request.Request(url, headers={'User-Agent':'Emergency-AI-update-check'})
    with urllib.request.urlopen(request, timeout=max(.01, timeout)) as response:
        if urllib.parse.urlsplit(response.url).scheme != 'https':
            raise ValueError('Insecure metadata redirect')
        data = response.read(MAX_METADATA + 1)
    if len(data) > MAX_METADATA:
        raise ValueError('Metadata exceeds size limit')
    return data.decode('utf-8')


def _json(url, timeout):
    return json.loads(_text(url, timeout))


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            text=True, timeout=2, check=False)
    return result.stdout.strip() if result.returncode == 0 else ''


def _row(component, installed=None, status='unknown', reason='Identity is not recorded.'):
    return dict(component=component, status=status, installed=installed, candidate=None, reason=reason)


def _report(rows):
    return {'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'components':rows}


def inventory(root):
    """Inspect local metadata and files without executing installed components."""
    root = Path(root)
    manifest = _read(root / 'runtime/installation.json')
    app = manifest.get('app') or {}
    if (root / '.git').exists():
        try:
            branch = _git(root, 'symbolic-ref', '--short', 'HEAD')
            remote = _git(root, 'config', f'branch.{branch}.remote')
            merge = _git(root, 'config', f'branch.{branch}.merge')
            app = {'kind':'git', 'commit':_git(root, 'rev-parse', 'HEAD'), 'branch':merge[len('refs/heads/'):] if merge.startswith('refs/heads/') else merge,
                   'remote':remote, 'remote_url':_git(root, 'remote', 'get-url', remote) if remote else '',
                   'dirty':bool(_git(root, 'status', '--porcelain')), 'local_branch':branch}
        except (OSError, subprocess.TimeoutExpired):
            app = {}
    elif app:
        app = dict(app, kind='standalone')
    rows = [_row('app', app or None)]
    recorded = manifest.get('components') or {}
    settings = _read(root / 'config/settings.json')
    settings.update(_read(root / 'config/settings.local.json'))
    model_meta = recorded.get('model') or {}
    model_catalog = _read(root / 'config/models.json').get('models', [])
    models = sorted((root / 'models').glob('*.gguf'))
    for path in models:
        relative = path.relative_to(root).as_posix()
        meta = model_meta if model_meta.get('path') == relative else {}
        recognized = next((m.get('id') for m in model_catalog if m.get('file') == path.name), None)
        rows.append(_row('model', dict(meta, path=relative, file=path.name, size=path.stat().st_size,
                                      recognized_model=recognized)))
    if not models:
        rows.append(_row('model', status='manual' if settings.get('llm_backend') in ('ollama','external','openai') else 'unknown',
                         reason='Externally managed or no local model installed.'))
    releases = sorted((root / 'runtime/llama.cpp').glob('**/release.json'))
    for path in releases:
        meta = _read(path)
        folder = path.parent.name
        backend = next((b for b in ('cuda', 'vulkan') if folder.endswith('-' + b)), 'cpu')
        plat = folder[:-(len(backend)+1)] if backend != 'cpu' else folder
        rows.append(_row('llama', dict(meta, platform=plat, backend=backend, path=path.parent.relative_to(root).as_posix())))
    if not releases:
        rows.append(_row('llama', reason='No managed llama release identity.'))
    for component in ('python','kiwix-tools','document-tools','drivers'):
        metadata = recorded.get(component)
        if not metadata and component in ('python','kiwix-tools'):
            relative = 'runtime/' + component + '/' + platform_key()
            metadata = _read(root / relative / 'installation.json')
            if metadata:
                metadata.update(path=relative, platform=platform_key())
        rows.append(_row(component, metadata, 'manual', 'Host-managed or artifact provenance is insufficient for automatic updates.'))
    zim_meta = recorded.get('kiwix-data') or []
    zim_catalog = _read(root / 'config/zims.json')
    if isinstance(zim_meta, dict):
        zim_meta = [zim_meta]
    for path in sorted((root / 'zim').glob('*.zim')):
        relative = path.relative_to(root).as_posix()
        meta = next((m for m in zim_meta if m.get('path') == relative), {})
        historical = next((a.get('snapshot') for a in zim_catalog.get('archives', [])
                           if Path(urllib.parse.urlsplit(a.get('url', '')).path).name == path.name), None)
        recognized = next((z['name'] for z in zim_catalog.get('zims', [])
                           if re.fullmatch(re.escape(z['name'] + ('_' + z['variant'] if z.get('variant') else ''))
                                           + r'_\d{4}-\d{2}\.zim', path.name)), None)
        rows.append(_row('kiwix-data', dict(meta, path=relative, file=path.name, size=path.stat().st_size,
                                          recognized_collection=recognized, historical_snapshot=historical)))
    if not any(r['component']=='kiwix-data' for r in rows):
        rows.append(_row('kiwix-data', reason='No local ZIM installed.'))
    return _report(rows)


def _candidate(identity, url, size=None, sha256=None, platform=None, **extra):
    return dict(identity=identity, url=url, size=size, sha256=sha256, platform=platform, **extra)


def _app(row, timeout, fetch_json=None):
    fetch_json = fetch_json or _json
    installed = row['installed'] or {}
    repo, branch = OFFICIAL_REPO, 'main'
    if installed.get('kind') == 'git':
        match = re.fullmatch(r'(?:https://github.com/|git@github.com:)([\w.-]+/[\w.-]+?)(?:\.git)?', installed.get('remote_url',''))
        if not match or not installed.get('branch'):
            row.update(status='manual', reason='Git upstream is absent or is not a supported GitHub repository.')
            return row
        repo, branch = match[1], installed['branch']
    data = fetch_json(f'https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(branch, safe="")}', timeout)
    commit = data.get('sha','')
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Provider did not return an immutable commit')
    row['candidate'] = _candidate(commit, f'https://github.com/{repo}/archive/{commit}.tar.gz',
                                  kind=installed.get('kind','standalone'), repository=repo, branch=branch, commit=commit)
    if not installed.get('commit'):
        row.update(status='blocked', reason='Standalone baseline is unknown; reviewed baseline import is required.')
    elif installed.get('dirty'):
        row.update(status='blocked', reason='Git working tree contains local changes.')
    else:
        row.update(status='current' if commit == installed['commit'] else 'available', reason='Immutable branch build; not a certified release.')
    return row


def _model(row, app, timeout, fetch_json=None):
    fetch_json = fetch_json or _json
    installed = row['installed'] or {}
    if not installed.get('id') or not installed.get('sha256'):
        reason = ('Recognized catalog model %s; installed bytes are not verified. Run --adopt --component model with the same --root.'
                  % installed['recognized_model']) if installed.get('recognized_model') else 'Custom or unverified model; no replacement is inferred from its filename.'
        row.update(reason=reason)
        return row
    candidate_app = app.get('candidate') or {}
    if not candidate_app.get('commit'):
        raise ValueError('Pinned application catalog is unavailable')
    url = f'https://raw.githubusercontent.com/{candidate_app["repository"]}/{candidate_app["commit"]}/config/models.json'
    catalog = fetch_json(url, timeout)
    model = next((m for m in catalog.get('models',[]) if m.get('id') == installed['id'] and m.get('file') == installed.get('file')), None)
    if not model:
        row.update(status='manual', reason='No same-model, same-quantization catalog candidate.')
        return row
    if not re.fullmatch('[0-9a-f]{64}', model.get('sha256','')) or not re.fullmatch('[0-9a-f]{40}', model.get('revision','')) or model['revision'] not in model.get('url',''):
        raise ValueError('Model candidate lacks pinned revision and checksum')
    row['candidate'] = _candidate(model['revision'], model['url'], model.get('size_bytes'), model['sha256'],
                                  id=model['id'], file=model['file'], revision=model['revision'], path=installed['path'])
    row.update(status='current' if installed['sha256']==model['sha256'] else 'available', reason='Project catalog at immutable app commit; same model and quantization.')
    return row


def _llama(row, timeout, fetch_json=None):
    fetch_json = fetch_json or _json
    from .prepare import _llama_pick, _cuda_pick
    installed = row['installed'] or {}
    if not installed.get('tag'):
        return row
    if installed['platform'] != platform_key():
        row.update(status='manual', reason='Foreign platform; execution checks cannot run on this host.')
        return row
    releases = fetch_json('https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10', timeout)
    for release in releases:
        numbered_stream = bool(re.fullmatch(r'b\d+', installed['tag']) and
                               re.fullmatch(r'b\d+', release.get('tag_name', '')))
        if release.get('draft') or (release.get('prerelease') and not numbered_stream):
            continue
        assets = release.get('assets', [])
        tuples = [(a['name'],a['browser_download_url'],a.get('size')) for a in assets]
        backend = installed.get('backend','cpu')
        pair = _cuda_pick(installed['platform'],tuples) if backend=='cuda' else None
        selected = pair[0] if pair else _llama_pick(installed['platform'], tuples, backend) if backend!='cuda' else None
        if not selected:
            continue
        asset = next(a for a in assets if a['name']==selected[0])
        sha = (asset.get('digest') or '').replace('sha256:', '', 1)
        row['candidate'] = _candidate(release['tag_name'], selected[1], selected[2], sha if re.fullmatch('[0-9a-f]{64}',sha) else None,
                                      installed['platform'], tag=release['tag_name'], asset=selected[0], backend=backend,
                                      path=installed['path'], prerelease=bool(release.get('prerelease')))
        if pair:
            companion = next(a for a in assets if a['name']==pair[1][0])
            digest = (companion.get('digest') or '').replace('sha256:', '', 1)
            row['candidate']['runtime_asset'] = _candidate(companion['name'], companion['browser_download_url'], companion.get('size'), digest if re.fullmatch('[0-9a-f]{64}',digest) else None, installed['platform'])
        verified = row['candidate']['sha256'] and (not pair or row['candidate']['runtime_asset']['sha256'])
        row.update(status=('current' if installed['tag']==release['tag_name'] and installed['asset']==selected[0] else 'available') if verified else 'manual', reason='Matched platform/backend release.' if verified else 'Publisher SHA-256 unavailable; explicit weaker-verification decision required.')
        if release.get('prerelease'):
            row['reason'] += ' Numbered llama.cpp build stream; GitHub labels these builds as prerelease.'
        return row
    row.update(status='unavailable', reason='No matching platform/backend release.')
    return row


def check(root, timeout=30, components=None):
    """Return partial results within one deadline; workers never write installation files."""
    deadline = time.monotonic() + max(0, timeout)
    selected = set(components or ())
    if selected & {'model', 'document-tools'}:
        selected.add('app')
    requests = {}
    request_lock = threading.Lock()

    def fetch_json(url, request_timeout):
        # Share both responses and failures between workers during this check only.
        with request_lock:
            owner = url not in requests
            future = requests.setdefault(url, Future())
        if owner:
            try:
                future.set_result(_json(url, request_timeout))
            except Exception as exc:
                future.set_exception(exc)
        return future.result(timeout=max(0, deadline-time.monotonic()))

    local = queue.Queue()

    def inspect():
        try:
            local.put(inventory(root))
        except Exception:
            local.put(None)

    threading.Thread(target=inspect, daemon=True).start()
    try:
        result = local.get(timeout=max(0, deadline-time.monotonic()))
    except queue.Empty:
        result = None
    if result is None:
        return _report([_row(c, status='unavailable', reason='Local inventory unavailable within deadline.')
                        for c in ('app','model','llama','python','kiwix-tools','document-tools','kiwix-data','drivers')
                        if not selected or c in selected])
    rows = result['components'] = [r for r in result['components']
                                   if not selected or r['component'] in selected]
    done = queue.Queue()
    app_ready = threading.Event()
    app_result = {}

    def worker(index, original):
        row = copy.deepcopy(original)
        try:
            remaining = lambda: max(.01, deadline-time.monotonic())
            if row['component']=='app':
                row = _app(row, remaining(), fetch_json)
                app_result.update(row)
            elif row['component']=='model':
                app_ready.wait(remaining())
                row = _model(row, app_result, remaining(), fetch_json)
            elif row['component']=='llama':
                row = _llama(row, remaining(), fetch_json)
            elif row['component'] in ('python','kiwix-tools','document-tools'):
                if row['component']=='document-tools':
                    app_ready.wait(remaining())
                row = _tool(row, app_result, remaining(), Path(root), fetch_json)
            elif row['component']=='kiwix-data':
                row = _zim(Path(root), row, remaining())
        except urllib.error.HTTPError as exc:
            host = urllib.parse.urlsplit(exc.url).hostname or 'provider'
            reason = f'Metadata unavailable from {host} (HTTP {exc.code}).'
            headers = {key.lower(): value for key, value in (exc.headers or {}).items()}
            if exc.code == 429 or (exc.code == 403 and headers.get('x-ratelimit-remaining') == '0'):
                reason = f'{host} API rate limit reached (HTTP {exc.code}).'
                try:
                    reset = int(headers.get('x-ratelimit-reset', ''))
                    reset_time = datetime.datetime.fromtimestamp(reset, datetime.timezone.utc)
                except (ValueError, OverflowError, OSError):
                    reason += ' Retry after the provider rate limit resets.'
                else:
                    row['retry_at'] = reset
                    reason += f' Retry after {reset_time:%Y-%m-%d %H:%M:%S UTC}.'
            row.update(status='unavailable', reason=reason, http_status=exc.code, candidate=None)
        except Exception as exc:
            row.update(status='unavailable', reason=f'Metadata unavailable ({type(exc).__name__}).', candidate=None)
        finally:
            if row['component']=='app':
                app_ready.set()
        done.put((index,row))

    pending = set()
    for i, row in enumerate(rows):
        if row['component'] in ('app','model','llama','kiwix-data','python','kiwix-tools','document-tools'):
            pending.add(i)
            threading.Thread(target=worker,args=(i,row),daemon=True).start()
    while pending:
        try:
            i, row = done.get(timeout=max(0,deadline-time.monotonic()))
        except queue.Empty:
            break
        rows[i] = row
        pending.remove(i)
    for i in pending:
        rows[i] = dict(rows[i], status='unavailable', candidate=None, reason='Metadata deadline exceeded.')
    return result


def _zim(root, row, timeout):
    installed = row['installed'] or {}
    if installed.get('historical_snapshot') and not installed.get('sha256'):
        row.update(status='manual', reason='Recognized fixed historical snapshot %s; no automatic refresh. Installed integrity is not recorded.' % installed['historical_snapshot'])
        return row
    if not installed.get('collection') or not installed.get('sha256'):
        reason = ('Recognized catalog collection %s; installed edition bytes are not verified. Run --adopt --component kiwix-data with the same --root.'
                  % installed['recognized_collection']) if installed.get('recognized_collection') else 'Custom or unverified archive; collection identity is not recorded.'
        row.update(reason=reason)
        return row
    if installed.get('fixed') or installed.get('snapshot'):
        row.update(status='current', reason='Fixed historical archive; automatic refresh is disabled.')
        return row
    config = _read(root / 'config/zims.json')
    url = config.get('catalog_url','https://library.kiwix.org/catalog/v2/entries')
    url += '?' + urllib.parse.urlencode({'name':installed['collection'],'count':100})
    catalog = ET.fromstring(_text(url, timeout))
    ns = {'a':'http://www.w3.org/2005/Atom','m':'urn:ietf:params:xml:ns:metalink'}
    prefix = installed['collection'] + ('_'+installed['variant'] if installed.get('variant') else '')
    pattern = re.compile(re.escape(prefix)+r'_(\d{4}-\d{2})\.zim$')
    candidates = []
    for entry in catalog.findall('a:entry',ns):
        for link in entry.findall('a:link',ns):
            href = link.get('href','')
            if link.get('type')!='application/x-zim' or not href.endswith('.meta4'):
                continue
            name = Path(urllib.parse.urlsplit(href[:-6]).path).name
            if pattern.fullmatch(name):
                candidates.append((name,href))
    if not candidates:
        raise ValueError('No exact collection and variant candidate')
    name, meta_url = max(candidates)
    meta = ET.fromstring(_text(meta_url, timeout)).find('m:file',ns)
    if meta is None or meta.get('name') != name:
        raise ValueError('Metalink filename mismatch')
    size = int(meta.findtext('m:size','0',ns))
    sha = meta.findtext("m:hash[@type='sha-256']",'',ns)
    if size<=0 or not re.fullmatch('[0-9a-fA-F]{64}',sha):
        raise ValueError('Missing metalink size/SHA-256')
    row['candidate'] = _candidate(name,meta_url[:-6],size,sha.lower(), collection=installed['collection'], variant=installed.get('variant'), file=name, path=installed['path'], destination='zim/'+name)
    if name==installed['file'] and installed['sha256'].lower()!=sha.lower():
        row.update(status='unknown',reason='Same archive filename has a different publisher checksum; identity requires review.')
    else:
        row.update(status='available' if name>installed['file'] else 'current', reason='Exact collection and variant with metalink SHA-256.')
    if row['status']=='available':
        from .upgrade_assets import _binary, document_indexes_present
        pdf=any(entry.get('name')==installed['collection'] and entry.get('document_format')=='nautilus' for entry in config.get('zims',[]))
        if pdf or installed.get('document_format')=='nautilus' or installed.get('index_path') or document_indexes_present(root):
            row.update(status='manual',reason='This PDF/indexed collection requires a reviewed index migration before replacement.')
        elif _read(root/'config/source-policy.json').get('rules'):
            row.update(status='manual',reason='Version-scoped source policy requires reviewed archive mapping migration.')
        elif _binary(root/'runtime/kiwix-tools'/platform_key(),'kiwix-serve') is None:
            row.update(status='manual',reason='Install managed kiwix-serve before upgrading archives; archive-open and representative-read verification is required.')
    return row


def _tool(row, app, timeout, root=None, fetch_json=None):
    fetch_json = fetch_json or _json
    installed = row['installed'] or {}
    if not installed:
        return row
    plat = installed.get('platform', platform_key())
    component = row['component']
    if plat != platform_key():
        row.update(status='manual',reason='Foreign platform; activation and execution checks require a matching host.')
        return row
    if component=='document-tools':
        commit = app.get('candidate') or {}
        if not commit.get('commit'):
            raise ValueError('Pinned tool catalog unavailable')
        url = 'https://raw.githubusercontent.com/{}/{}/config/document-tools.json'.format(commit['repository'],commit['commit'])
        data = fetch_json(url,timeout).get('supported_platforms',{}).get(plat)
        if not data:
            row.update(reason='No supported document tools for this platform.')
            return row
        row['candidate'] = dict(data, identity=data['version'], platform=plat, path=installed.get('path'))
        from .upgrade_assets import document_indexes_present
        complete=all(data.get(key) for key in ('root','binary','pdfinfo','sha256','size'))
        indexed=root is None or document_indexes_present(root)
        row.update(status='current' if installed.get('version')==data['version'] else 'available' if complete and not indexed else 'manual', reason='Verified extractor candidate; no existing document indexes.' if complete and not indexed else 'Extractor metadata is incomplete or existing document indexes need migration.')
    elif component=='python':
        from .prepare import PYTHON_TRIPLES
        triple = PYTHON_TRIPLES.get(plat)
        if not triple:
            return row
        release = fetch_json('https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest',timeout)
        version = re.match(r'cpython-(3\.\d+)\.',installed.get('asset',''))
        if not version:
            row.update(reason='Python installed minor version is unknown; no interpreter switch is inferred.')
            return row
        pattern = re.compile(r'cpython-'+re.escape(version[1])+r'\.\d+\+\d+-'+re.escape(triple)+r'-install_only\.tar\.gz$')
        assets = [a for a in release.get('assets',[]) if pattern.fullmatch(a['name'])]
        if not assets:
            row.update(status='unavailable',reason='No same-minor Python asset for this platform triple.')
            return row
        asset = max(assets,key=lambda a:tuple(int(n) for n in re.findall(r'\d+',a['name'].split('+')[0])))
        sha = asset.get('digest','').replace('sha256:','',1)
        row['candidate'] = _candidate(asset['name'],asset['browser_download_url'],asset.get('size'),sha if re.fullmatch('[a-f0-9]{64}',sha) else None,plat,asset=asset['name'],path=installed.get('path'))
        in_use=True
        if root is not None and installed.get('path'):
            try:
                Path(sys.executable).resolve().relative_to((root/installed['path']).resolve())
            except ValueError:
                in_use=False
        legacy_links=bool(root is not None and installed.get('path') and any(p.is_symlink() for p in (root/installed['path']).rglob('*')))
        if legacy_links:
            row.update(status='manual',reason='Existing Python contains symlinks; a verified materialized baseline is required before transactional activation.')
            return row
        verified=bool(row['candidate']['sha256'] and asset.get('size'))
        row.update(status='current' if installed.get('asset')==asset['name'] else 'available' if verified and not in_use else 'manual',reason='Verified same-minor Python; current interpreter is independent.' if verified and not in_use else 'Use separate system Python for activation; publisher digest/size are required.')
    elif component=='kiwix-tools':
        from .prepare import KIWIX_ASSETS, KIWIX_TOOLS_DIR
        listing = _text(KIWIX_TOOLS_DIR,timeout)
        keys = KIWIX_ASSETS.get(plat,[])[:1]
        matches=[]
        for name in re.findall(r'href="(kiwix-tools_[^"]+\.(?:zip|tar\.gz))"',listing):
            for key in keys:
                match = re.fullmatch('kiwix-tools_'+re.escape(key)+r'-(\d+(?:\.\d+)*)\.(?:zip|tar\.gz)',name)
                if match:
                    matches.append((tuple(int(n) for n in match[1].split('.')),name))
        if not matches:
            row.update(status='unavailable',reason='No exact-platform Kiwix tools candidate.')
            return row
        _, name=max(matches)
        row['candidate']=_candidate(name,KIWIX_TOOLS_DIR+name,platform=plat,asset=name,path=installed.get('path'))
        row.update(status='current' if installed.get('asset')==name else 'manual',reason='Publisher listing compared; trusted size and SHA-256 are unavailable for automatic installation.')
    return row
