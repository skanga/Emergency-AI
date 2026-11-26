"""Project-pinned external tool provenance and capability checks."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse

from .config import platform_key
from .upgrade_assets import _download, _extract, _hash, _path


def catalog(component, platform):
    root=Path(__file__).resolve().parent.parent
    filename='config/runtime-tools.json' if component=='kiwix-tools' else 'config/document-tools.json'
    raw=(root/filename).read_bytes()
    data=json.loads(raw)
    entries=data.get('kiwix-tools',{}) if component=='kiwix-tools' else data.get('supported_platforms',{})
    entry=dict(entries.get(platform) or {})
    host='download.kiwix.org' if component=='kiwix-tools' else 'dl.xpdfreader.com'
    url=urllib.parse.urlsplit(entry.get('url',''))
    if (component not in ('kiwix-tools','document-tools') or url.scheme!='https' or url.hostname!=host
            or url.username or url.password or url.port not in (None,443)
            or not re.fullmatch('[a-f0-9]{64}',entry.get('sha256',''))
            or not isinstance(entry.get('size'),int) or entry['size']<=0):
        raise ValueError('No reviewed tool artifact for this component/platform')
    entry.update(platform=platform,verification='project-pinned-sha256',catalog=filename,
                 catalog_sha256=hashlib.sha256(raw).hexdigest())
    entry.setdefault('asset',Path(url.path).name)
    return entry


def _files(folder):
    result={}
    for path in folder.rglob('*'):
        name=path.relative_to(folder).as_posix()
        _path(folder,name)
        if path.is_file():result[name]=_hash(path)
        elif not path.is_dir():raise ValueError('Unsupported tool file: '+name)
    return result


def recognized(root, component, platform):
    try:entry=catalog(component,platform)
    except (OSError,ValueError):return None
    relative=('runtime/kiwix-tools/'+platform if component=='kiwix-tools' else 'runtime/document-tools/'+entry['root'])
    if not (Path(root)/relative).is_dir():return None
    return {'path':relative,'platform':platform,'recognized_version':entry['version']}


def verify_installed(root, installed):
    relative=installed['path']
    current={relative+'/'+name:sha for name,sha in _files(_path(root,relative)).items() if name!='installation.json'}
    if not installed.get('files') or current!=installed['files']:
        raise ValueError('Installed tool files differ from recorded provenance; review before replacement')


def adopt_tool(root, component):
    entry=catalog(component,platform_key())
    relative=('runtime/kiwix-tools/'+platform_key() if component=='kiwix-tools' else 'runtime/document-tools/'+entry['root'])
    installed=_path(root,relative)
    nested=_path(installed,entry['root']) if component=='kiwix-tools' and entry.get('root') else installed
    content=nested if nested.is_dir() else installed
    with tempfile.TemporaryDirectory(prefix='verify-tool-') as temp:
        stage=Path(temp);fresh=stage/'source'
        _extract(_download(entry,stage),fresh)
        expected=_files(_path(fresh,entry['root']) if entry.get('root') else fresh)
        actual=_files(content)
        if content==installed:actual.pop('installation.json',None)
        if not expected or actual!=expected:
            raise ValueError('Installed tool files differ from the reviewed artifact')
        files={relative+'/'+name:sha for name,sha in _files(installed).items() if name!='installation.json'}
        expected_names={relative+'/'+(entry['root']+'/' if content!=installed else '')+name for name in expected}
        if set(files)!=expected_names:
            raise ValueError('Installed tool directory differs from the reviewed artifact')
        verify_tool(root,component,content,entry)
    return dict(entry,path=relative,files=files,identity=entry['version'])


def _pdf_bytes():
    text=b'BT /F1 12 Tf 72 720 Td (Emergency AI tool verification) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
             b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
             b'<< /Length '+str(len(text)).encode()+b' >>\nstream\n'+text+b'\nendstream']
    body=b'%PDF-1.4\n';offsets=[0]
    for index,obj in enumerate(objects,1):
        offsets.append(len(body));body+=f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(body);body+=b'xref\n0 6\n0000000000 65535 f \n'
    body+=b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    return body+f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def verify_tool(root, component, folder, entry):
    from .upgrade_assets import verify_runtime,verify_zim,verify_document
    if component=='kiwix-tools':
        verify_runtime(folder,'kiwix-serve')
        for archive in sorted((Path(root)/'zim').glob('*.zim')):
            verify_zim(root,archive,runtime=folder)
    else:
        verify_document(folder,entry)
        with tempfile.TemporaryDirectory(prefix='pdf-probe-') as temp:
            pdf=Path(temp)/'probe.pdf';pdf.write_bytes(_pdf_bytes())
            subprocess.run([str(_path(folder,entry['pdfinfo'])),str(pdf)],capture_output=True,check=True,timeout=15)
            result=subprocess.run([str(_path(folder,entry['binary'])),'-enc','UTF-8',str(pdf),'-'],capture_output=True,check=True,timeout=15)
            if b'Emergency AI tool verification' not in result.stdout:
                raise ValueError('PDF text extraction health check failed')
