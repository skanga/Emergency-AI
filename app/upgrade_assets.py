"""Stage, verify and transact explicitly selected managed asset updates."""
import hashlib
import gzip
import json
import os
import re
import shutil
import sys
import posixpath
import subprocess
import tarfile
import tempfile
import socket
import time
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath

from .config import platform_key
from .updates import _read


def _path(root, relative):
    parts = PurePosixPath(relative).parts
    if not parts or PurePosixPath(relative).is_absolute() or any(p in ('..','.') for p in parts) or '\\' in relative or ':' in relative:
        raise ValueError('Invalid managed path')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Managed paths must not traverse a symlink')
    return path


def _hash(path):
    digest = hashlib.sha256()
    with open(path,'rb') as source:
        for block in iter(lambda: source.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def _download(candidate, stage):
    from .prepare import download
    url = candidate.get('url','')
    sha = candidate.get('sha256','') or ''
    size = candidate.get('size')
    if urllib.parse.urlsplit(url).scheme != 'https' or not re.fullmatch('[a-fA-F0-9]{64}',sha) or not isinstance(size,int) or size<=0:
        raise ValueError('Artifact requires HTTPS, exact size and SHA-256')
    name = Path(urllib.parse.urlsplit(url).path).name
    if not name:
        raise ValueError('Missing artifact filename')
    path = stage / name
    download(url,str(path),expected_size=size,sha256=sha)
    if not path.is_file() or path.stat().st_size!=size or _hash(path)!=sha.lower():
        raise ValueError('Downloaded artifact integrity check failed')
    return path


def _materialize_tar(archive, destination):
    # Link targets require random access. Rewinding gzip for every link repeatedly
    # decompresses the distribution, so spool once before resolving members.
    with open(archive, 'rb') as stream:
        compressed = stream.read(2) == b'\x1f\x8b'
    if compressed:
        with tempfile.TemporaryDirectory(dir=Path(destination).parent) as temp:
            raw = Path(temp)/'source.tar'
            with gzip.open(archive, 'rb') as source, raw.open('wb') as target:
                shutil.copyfileobj(source, target, length=1024*1024)
            return _materialize_tar(raw, destination)
    with tarfile.open(archive) as source,tarfile.open(destination,'w') as target:
        for member in source.getmembers():
            _path(Path(destination).parent,member.name.rstrip('/'))
            resolved=member
            seen=set()
            while resolved.issym() or resolved.islnk():
                if resolved.name in seen:
                    raise ValueError('Cyclic archive link')
                seen.add(resolved.name)
                name=posixpath.normpath(posixpath.join(posixpath.dirname(resolved.name),resolved.linkname) if resolved.issym() else resolved.linkname)
                _path(Path(destination).parent,name)
                resolved=source.getmember(name)
            if not resolved.isfile() and not resolved.isdir():
                raise ValueError('Unsupported archive special file')
            if member.issym() or member.islnk():
                if not resolved.isfile():
                    raise ValueError('Archive directory symlinks require manual installation')
                materialized=tarfile.TarInfo(member.name)
                materialized.mode=resolved.mode
                materialized.size=resolved.size
                target.addfile(materialized,source.extractfile(resolved))
            else:
                target.addfile(member,source.extractfile(member) if member.isfile() else None)


def _extract(archive, destination, materialize_links=False):
    if materialize_links and not zipfile.is_zipfile(archive):
        with tempfile.TemporaryDirectory(dir=Path(archive).parent) as temp:
            sanitized = Path(temp)/'materialized.tar'
            _materialize_tar(archive, sanitized)
            return _extract(sanitized, destination)
    from .prepare import extract
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as source:
            entries = [(m.filename, (m.external_attr >> 16) & 0o170000 == 0o120000) for m in source.infolist()]
    else:
        with tarfile.open(archive) as source:
            entries = [(m.name, not (m.isfile() or m.isdir())) for m in source.getmembers()]
    for name, unsafe in entries:
        _path(destination,name.rstrip('/'))
        if unsafe:
            raise ValueError('Archive links and special files are unsupported')
    extract(str(archive),str(destination))


def _binary(folder, name):
    matches = sorted(folder.rglob(name + ('.exe' if os.name=='nt' else '')))
    return next((p for p in matches if p.is_file() and not p.is_symlink()),None)


def verify_runtime(folder, executable='llama-server', backend=None):
    from .launcher import _env_for
    binary = _binary(Path(folder),executable)
    if binary is None:
        raise ValueError('Required runtime executable is absent: '+executable)
    subprocess.run([str(binary),'--version'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=30,env=_env_for(str(binary),backend))
    return binary


def verify_model(root, model, runtime=None, backend=None):
    """Require GGUF plus bounded generation with a same-host llama CLI."""
    with open(model,'rb') as stream:
        if stream.read(4)!=b'GGUF':
            raise ValueError('Model is not a GGUF file')
    from .launcher import _env_for
    folder, backend = (Path(runtime),backend) if runtime else _model_runtime(Path(root))
    binary = _binary(folder,'llama-cli')
    if binary is None:
        raise ValueError('Model-load verification needs a managed llama-cli; install a compatible runtime first')
    command=[str(binary),'-m',str(model),'-n','1','-p','Hello','-c','512','--no-warmup']
    if backend in ('cuda','vulkan','metal'):
        command += ['--n-gpu-layers','auto','--fit','on']
    subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=120,env=_env_for(str(binary),backend))


def _active_model(root):
    settings = _read(root/'config/settings.json')
    settings.update(_read(root/'config/settings.local.json'))
    name = settings.get('model_file')
    if name:
        path = _path(root,'models/'+name)
        if not path.is_file():
            raise ValueError('Selected model is missing')
        return path
    models = sorted((root/'models').glob('*.gguf'))
    if not models:
        return None
    catalog=_read(root/'config/models.json')
    default=next((m.get('file') for m in catalog.get('models',[]) if m.get('id')==catalog.get('default')),None)
    return next((p for p in models if p.name==default),max(models,key=lambda p:p.stat().st_size))


def _runtime_files(root, relative, preserve_file_links=False):
    """Validate the old tree before replacement; only internal file links are supported."""
    destination = _path(root, relative)
    changes = {}
    for path in destination.rglob('*'):
        if preserve_file_links and path.is_symlink():
            _path(root, path.parent.relative_to(root).as_posix())
            path.resolve(strict=True).relative_to(destination.resolve())
            if not path.is_file():
                raise ValueError('Runtime directory links are unsupported')
        else:
            _path(root, path.relative_to(root).as_posix())
        if path.is_file():
            changes[path.relative_to(root).as_posix()] = None
        elif not path.is_dir():
            raise ValueError('Runtime special files are unsupported')
    return changes


def _runtime_changes(root, installed, candidate, stage, component):
    relative = installed['path']
    expected = {'llama':'runtime/llama.cpp/','kiwix-tools':'runtime/kiwix-tools/','document-tools':'runtime/document-tools/'}[component]
    if not relative.startswith(expected):
        raise ValueError('Unsupported managed runtime path')
    destination = _path(root,relative)
    if candidate.get('platform') != platform_key():
        raise ValueError('Runtime platform does not match this host')
    archive = _download(candidate,stage)
    fresh = stage/'extracted'
    _extract(archive,fresh,materialize_links=component=='llama')
    executable = {'llama':'llama-server','kiwix-tools':'kiwix-serve','document-tools':'pdftotext'}[component]
    binary = _binary(fresh,executable)
    if binary is None:
        raise ValueError('Required runtime executable is absent')
    entries=list(fresh.iterdir())
    content=entries[0] if len(entries)==1 and entries[0].is_dir() else fresh
    if candidate.get('runtime_asset'):
        companion_stage=stage/'companion'
        companion_stage.mkdir()
        companion=stage/'companion-extracted'
        _extract(_download(candidate['runtime_asset'],companion_stage),companion,materialize_links=True)
        for library in companion.rglob('*'):
            if library.is_file() and (library.suffix in ('.dll','.dylib','.so') or '.so.' in library.name):
                target=binary.parent/library.name
                if target.exists():
                    raise ValueError('Companion runtime library collision: '+library.name)
                shutil.copy2(library,target)
        preserved=content/'companion-distribution'
        if preserved.exists():
            raise ValueError('Companion distribution path collision')
        shutil.copytree(companion,preserved)
    verify_runtime(content,executable,candidate.get('backend'))
    if component=='kiwix-tools':
        from .upgrade_tools import verify_tool
        verify_tool(root,component,content,candidate)
    if component=='document-tools':
        raise ValueError('Document tool activation requires a reviewed extractor/index migration')
    if component=='llama':
        model=_active_model(root)
        if model is not None:
            verify_model(root,model,runtime=content,backend=candidate.get('backend'))
        (content/'release.json').write_text(json.dumps({'tag':candidate['tag'],'asset':candidate['asset'],'model_check':'passed' if model is not None else 'not_run: no local model'}),encoding='utf-8')
    changes = _runtime_files(root, relative, preserve_file_links=component in ('llama','python'))
    for path in content.rglob('*'):
        if path.is_file():
            changes[relative+'/'+path.relative_to(content).as_posix()]=str(path)
    return changes


def upgrade(root, record, allow_unverified=False):
    """Caller holds maintenance lock and has stopped affected managed services."""
    root=Path(root).absolute()
    component=record.get('component')
    installed=record.get('installed') or {}
    candidate=record.get('candidate') or {}
    if record.get('status')!='available' or not installed or not candidate:
        raise ValueError('An available, identified managed asset is required')
    if component=='python':
        destination=_path(root,installed.get('path',''))
        try:
            Path(sys.executable).resolve().relative_to(destination.resolve())
        except ValueError:
            pass
        else:
            raise ValueError('Use a separate system Python: python3 emergency.py upgrade --component python --yes; the running bundled interpreter cannot replace itself')
    if component not in ('model','llama','kiwix-tools','document-tools','kiwix-data','python'):
        raise ValueError('Unsupported managed asset component')
    if component in ('kiwix-tools','document-tools'):
        from .upgrade_tools import verify_installed
        verify_installed(root, installed)
    if component=='kiwix-data':
        if _read(root/'config/source-policy.json').get('rules'):
            raise ValueError('Version-scoped source policy requires reviewed archive migration')
        catalog=_read(root/'config/zims.json')
        pdf=any(z.get('name')==installed.get('collection') and z.get('document_format')=='nautilus' for z in catalog.get('zims',[]))
        if pdf or installed.get('document_format')=='nautilus' or installed.get('index_path'):
            raise ValueError('This collection requires an index migration before upgrade')
    if component=='python':
        _runtime_files(root, installed.get('path',''), preserve_file_links=True)
    old=_path(root,installed.get('path',''))
    if not old.exists():
        raise ValueError('Installed managed asset is missing')
    if component in ('model','kiwix-data'):
        if not installed.get('sha256') or _hash(old)!=installed['sha256']:
            raise ValueError('Installed asset differs from recorded identity')
    _path(root,'runtime/installation.json')
    _path(root,'runtime/upgrades')
    (root/'runtime/upgrades').mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='stage-',dir=str(root/'runtime/upgrades')) as temp:
        stage=Path(temp)
        if component=='model':
            if not installed['path'].startswith('models/') or candidate.get('id')!=installed.get('id') or candidate.get('file')!=installed.get('file'):
                raise ValueError('Model family/quantization changes require separate selection')
            artifact=_download(candidate,stage)
            verify_model(root,artifact)
            destination=installed['path']
            changes={destination:str(artifact)}
        elif component=='kiwix-data':
            from .prepare import _zim_checksum_valid
            if candidate.get('collection')!=installed.get('collection') or candidate.get('variant')!=installed.get('variant') or installed.get('fixed') or installed.get('snapshot'):
                raise ValueError('Archive collection/variant mismatch or fixed snapshot')
            destination=candidate.get('destination','')
            target=_path(root,destination)
            if not installed['path'].startswith('zim/') or not destination.startswith('zim/') or target.exists():
                raise ValueError('Archive destination must be a new managed ZIM path')
            artifact=_download(candidate,stage)
            if not _zim_checksum_valid(str(artifact)):
                raise ValueError('Archive embedded checksum failed')
            verify_zim(root,artifact)
            changes={installed['path']:None,destination:str(artifact)}
        elif component=='document-tools':
            destination='runtime/document-tools/'+candidate.get('root','')
            changes=_document_changes(root,installed,candidate,stage)
        elif component=='python':
            destination=installed['path']
            changes=_python_changes(root,installed,candidate,stage)
        else:
            destination=installed['path']
            changes=_runtime_changes(root,installed,candidate,stage,component)
        manifest=_read(root/'runtime/installation.json')
        manifest.setdefault('schema_version',1)
        components=manifest.setdefault('components',{})
        metadata=dict(candidate,path=destination)
        if component in ('kiwix-tools','document-tools'):
            metadata['files']={name:_hash(source) for name,source in changes.items() if name.startswith(destination+'/') and source is not None}
        if component=='kiwix-data':
            previous=components.get(component,[])
            if isinstance(previous,dict):
                previous=[previous]
            components[component]=[m for m in previous if m.get('path')!=installed['path']]+[metadata]
        else:
            components[component]=metadata
        manifest_path=stage/'installation.json'
        manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        changes['runtime/installation.json']=str(manifest_path)
        from upgrade_recovery import Transaction
        transaction=Transaction(root,component,preserve_file_links=component in ('llama','python'))
        def verify():
            if component=='model':
                verify_model(root,_path(root,destination))
            elif component=='llama':
                verify_runtime(_path(root,destination),backend=candidate.get('backend'))
                model=_active_model(root)
                if model is not None:
                    verify_model(root,model,runtime=_path(root,destination),backend=candidate.get('backend'))
            elif component=='kiwix-data':
                verify_zim(root,_path(root,destination))
            elif component=='document-tools':
                from .upgrade_tools import verify_tool
                verify_tool(root,component,_path(root,destination),candidate)
            elif component=='python':
                verify_python(_path(root,destination),candidate,root)
            elif component=='kiwix-tools':
                from .upgrade_tools import verify_tool
                verify_tool(root,component,_path(root,destination),candidate)
        return transaction.apply(changes,verify=verify)


def verify_python(folder,candidate,app_root=None):
    executable=Path(folder)/'python'/('python.exe' if os.name=='nt' else 'bin/python3')
    version=re.match(r'cpython-(3\.\d+)\.',candidate.get('asset',''))
    if not executable.is_file() or not version:
        raise ValueError('Python executable or version identity is missing')
    script="import sys,ssl,sqlite3,importlib; assert '.'.join(map(str,sys.version_info[:2])) == " + repr(version[1]) + "; ssl.create_default_context(); sqlite3.connect(':memory:').execute('select 1'); importlib.import_module('json')"
    subprocess.run([str(executable),'-I','-B','-c',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=30)
    if app_root is not None and (Path(app_root)/'emergency.py').is_file():
        probe = "import runpy,sys; root=sys.argv[1]; sys.path.insert(0,root); p=root+'/emergency.py'; sys.argv=[p,'--help']; runpy.run_path(p,init_globals={'_UPGRADE_BOOTSTRAP':True},run_name='__main__')"
        subprocess.run([str(executable),'-I','-B','-c',probe,str(app_root)],cwd=str(app_root),
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=30)



def _python_changes(root,installed,candidate,stage):
    relative=installed['path']
    if not relative.startswith('runtime/python/') or candidate.get('platform')!=platform_key():
        raise ValueError('Python requires an exact managed platform path')
    before=re.match(r'cpython-(3\.\d+)\.',installed.get('asset',''))
    after=re.match(r'cpython-(3\.\d+)\.',candidate.get('asset',''))
    if not before or not after or before[1]!=after[1]:
        raise ValueError('Python minor-version changes require a separate compatibility review')
    archive=_download(candidate,stage)
    sanitized=stage/'materialized.tar'
    fresh=stage/'python-extracted'
    _materialize_tar(archive, sanitized)
    _extract(sanitized,fresh)
    verify_python(fresh,candidate,root)
    (fresh/'installation.json').write_text(json.dumps({'complete':True,'asset':candidate['asset']}),encoding='utf-8')
    changes = _runtime_files(root, relative, preserve_file_links=True)
    for path in fresh.rglob('*'):
        if path.is_file():
            changes[relative+'/'+path.relative_to(fresh).as_posix()]=str(path)
    return changes


def document_indexes_present(root):
    settings=_read(root/'config/settings.json')
    settings.update(_read(root/'config/settings.local.json'))
    folder=Path(settings.get('document_index_dir',str(root/'indexes')))
    if not folder.is_absolute():
        folder=root/folder
    return folder.is_symlink() or (folder.exists() and any(folder.rglob('*')))


def verify_document(folder,candidate):
    required=[candidate['binary'],candidate['pdfinfo'],'README','COPYING','COPYING3','doc/pdftotext.1']
    for name in required:
        if not _path(Path(folder),name).is_file():
            raise ValueError('Document tools distribution is incomplete: '+name)
    for name in (candidate['binary'],candidate['pdfinfo']):
        result=subprocess.run([str(_path(Path(folder),name)),'-v'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=30)
        output=(result.stdout+result.stderr).decode('utf-8',errors='replace')
        expected=Path(name).name+' version '+candidate['version']
        if result.returncode not in (0,99) or not re.search(re.escape(expected)+r'(?:\s|$)',output):
            raise ValueError('Document tool version check failed: '+name)


def _document_changes(root,installed,candidate,stage):
    if document_indexes_present(root):
        raise ValueError('Existing document indexes require a reviewed extractor/index migration')
    if candidate.get('platform')!=platform_key() or not installed['path'].startswith('runtime/document-tools/'):
        raise ValueError('Document tools require a managed same-platform installation')
    destination='runtime/document-tools/'+candidate['root']
    new=_path(root,destination)
    if new.exists() and destination!=installed['path']:
        raise ValueError('Document tools destination already exists')
    fresh=stage/'document-extracted'
    _extract(_download(candidate,stage),fresh)
    content=_path(fresh,candidate['root'])
    from .upgrade_tools import verify_tool
    verify_tool(root,'document-tools',content,candidate)
    changes={}
    for path in _path(root,installed['path']).rglob('*'):
        _path(root,path.relative_to(root).as_posix())
        if path.is_file():
            changes[path.relative_to(root).as_posix()]=None
    for path in content.rglob('*'):
        if path.is_file():
            changes[destination+'/'+path.relative_to(content).as_posix()]=str(path)
    catalog_path=_path(root,'config/document-tools.json')
    catalog=_read(catalog_path)
    catalog.setdefault('supported_platforms',{})[candidate['platform']]={k:v for k,v in candidate.items() if k not in ('identity','platform','path','destination')}
    staged=stage/'document-tools.json'
    staged.write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    changes['config/document-tools.json']=str(staged)
    return changes


def _model_runtime(root):
    from .launcher import gpu_devices
    settings=_read(root/'config/settings.json')
    settings.update(_read(root/'config/settings.local.json'))
    preference=settings.get('llm_acceleration','auto')
    plat=platform_key()
    backends=(['metal'] if plat.startswith('macos-') else ['cuda','vulkan'])
    if preference!='auto':
        backends=[] if preference=='cpu' else ['cuda','vulkan'] if preference=='cuda' else [preference]
    for backend in backends:
        folder=root/'runtime/llama.cpp'/(plat if backend=='metal' else plat+'-'+backend)
        server=_binary(folder,'llama-server')
        if server is not None and gpu_devices(str(server),backend)[0]:
            return folder,backend
    return root/'runtime/llama.cpp'/plat,'cpu'


def verify_zim(root,archive,timeout=20,runtime=None,_address='127.0.0.1'):
    """Open the candidate alone and read its main entry through local Kiwix."""
    from .launcher import _env_for, _is_wsl
    from .kiwix import KiwixClient
    from .net import get_text
    binary=_binary(Path(runtime) if runtime is not None else Path(root)/'runtime/kiwix-tools'/platform_key(),'kiwix-serve')
    if binary is None:
        raise ValueError('Archive upgrade requires managed kiwix-serve for an archive-open and representative-read check')
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0))
        port=reserved.getsockname()[1]
    base='http://127.0.0.1:'+str(port)
    deadline=time.monotonic()+timeout
    with tempfile.TemporaryFile() as diagnostics:
        process=subprocess.Popen([str(binary),'--address',_address,'--port',str(port),str(archive)],
                                 stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=diagnostics,env=_env_for(str(binary)))
        try:
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    diagnostics.seek(0)
                    detail=diagnostics.read(2000).decode('utf-8',errors='replace').strip()
                    if _address=='127.0.0.1' and _is_wsl() and detail=='ERROR: IP address is not available on this system: 127.0.0.1':
                        print('Kiwix rejected WSL loopback; temporary health check will listen on all IPv4 interfaces and may be reachable from your network.')
                        return verify_zim(root,archive,timeout=timeout,runtime=runtime,_address='ipv4')
                    raise ValueError('Kiwix could not open '+Path(archive).name+': '+detail)
                client=KiwixClient(base)
                books=client.books(deadline=deadline)
                if books:
                    if len(books)!=1 or not books[0].get('content_url'):
                        raise ValueError('Candidate archive has no unambiguous main entry')
                    body=get_text(base+books[0]['content_url'],timeout=min(5,max(.01,deadline-time.monotonic())),deadline=deadline,allowed_origin=base)
                    if not body.strip():
                        raise ValueError('Candidate archive main entry is empty')
                    return
                time.sleep(min(.1,max(0,deadline-time.monotonic())))
            raise ValueError('Candidate archive open/read check timed out')
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
