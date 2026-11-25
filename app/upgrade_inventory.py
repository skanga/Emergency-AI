"""Explicit, read-only asset verification followed by transactional provenance adoption."""
import json
import re
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from .updates import _read, _text
from .upgrade_assets import _hash, _path


def _verify(path, size, digest):
    if not isinstance(size,int) or size<=0 or not re.fullmatch('[0-9a-fA-F]{64}',digest or ''):
        raise ValueError('Exact size and SHA-256 provenance are missing')
    if path.stat().st_size!=size or _hash(path)!=digest.lower():
        raise ValueError('Installed bytes differ from verified catalog identity')


def _model(root):
    catalog=_read(root/'config/models.json').get('models',[])
    settings=_read(root/'config/settings.json')
    settings.update(_read(root/'config/settings.local.json'))
    wanted=settings.get('model_file') or _read(root/'runtime/kit-info.json').get('model')
    if wanted:
        matches=[m for m in catalog if m.get('file')==wanted]
    else:
        matches=[m for m in catalog if (root/'models'/m.get('file','')).is_file()]
    if len(matches)!=1:
        raise ValueError('Select one installed catalog model before adoption; custom models remain unknown')
    model=matches[0]
    path=_path(root,'models/'+model['file'])
    revision=model.get('revision','')
    if not re.fullmatch('[a-f0-9]{40}',revision) or '/resolve/'+revision+'/' not in model.get('url',''):
        raise ValueError('Model catalog revision is not pinned')
    _verify(path,model.get('size_bytes'),model.get('sha256'))
    with open(path,'rb') as stream:
        if stream.read(4)!=b'GGUF':
            raise ValueError('Installed model is not GGUF')
    return dict(model,path=path.relative_to(root).as_posix(),size=model['size_bytes'])


def _official(url, hosts):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Archive metadata must come from an official HTTPS Kiwix host')
    return url


def _zim(root, path, catalog, timeout):
    from .prepare import _zim_checksum_valid
    _path(root,path.relative_to(root).as_posix())
    matches=[]
    for entry in catalog.get('zims',[]):
        prefix=entry['name']+('_'+entry['variant'] if entry.get('variant') else '')
        if re.fullmatch(re.escape(prefix)+r'_\d{4}-\d{2}\.zim',path.name):
            matches.append(entry)
    if len(matches)!=1:
        raise ValueError('Unknown collection, variant, or fixed archive; no identity inferred')
    entry=matches[0]
    base=_official(catalog.get('catalog_url','https://library.kiwix.org/catalog/v2/entries'),('library.kiwix.org',))
    url=base+'?'+urllib.parse.urlencode({'name':entry['name'],'count':100})
    ns={'a':'http://www.w3.org/2005/Atom','m':'urn:ietf:params:xml:ns:metalink'}
    feed=ET.fromstring(_text(url,timeout))
    meta_url=None
    for link in feed.findall('.//a:link',ns):
        href=link.get('href','')
        if link.get('type')=='application/x-zim' and Path(urllib.parse.urlsplit(href).path).name==path.name+'.meta4':
            meta_url=_official(href,('download.kiwix.org','archive.download.kiwix.org','lb.download.kiwix.org'))
            break
    if not meta_url:
        raise ValueError('Metadata for the exact installed edition is unavailable; newer editions cannot establish its identity')
    metalink=ET.fromstring(_text(meta_url,timeout)).find('m:file',ns)
    if metalink is None or metalink.get('name')!=path.name:
        raise ValueError('Metalink does not identify the installed filename')
    size=int(metalink.findtext('m:size','0',ns))
    digest=metalink.findtext("m:hash[@type='sha-256']",'',ns).lower()
    _verify(path,size,digest)
    if not _zim_checksum_valid(str(path)):
        raise ValueError('Installed archive embedded checksum is invalid')
    return dict(collection=entry['name'],variant=entry.get('variant'),lang=entry.get('lang'),
                document_format=entry.get('document_format'),file=path.name,path=path.relative_to(root).as_posix(),
                url=meta_url[:-6],size=size,sha256=digest)


def adopt(root, components, timeout=30):
    """Caller holds maintenance lock. Hash existing assets; never download asset bytes."""
    from upgrade_recovery import Transaction
    root=Path(root).absolute()
    if not components or set(components)-{'model','kiwix-data'}:
        raise ValueError('Adoption supports explicitly selected model and kiwix-data components')
    manifest=_read(root/'runtime/installation.json')
    _path(root,'runtime/installation.json')
    records=manifest.setdefault('components',{})
    manifest.setdefault('schema_version',1)
    result={'transaction_id':None,'adopted':[],'unknown':[]}
    if 'model' in components:
        try:
            model=_model(root)
            records['model']=model
            result['adopted'].append({'component':'model','path':model['path']})
        except (OSError,ValueError,KeyError) as exc:
            result['unknown'].append({'component':'model','path':None,'reason':str(exc)})
    if 'kiwix-data' in components:
        catalog=_read(root/'config/zims.json')
        existing=records.get('kiwix-data',[])
        if isinstance(existing,dict):
            existing=[existing]
        for path in sorted((root/'zim').glob('*.zim')):
            relative=path.relative_to(root).as_posix()
            try:
                record=_zim(root,path,catalog,timeout)
                existing=[m for m in existing if m.get('path')!=relative]+[record]
                result['adopted'].append({'component':'kiwix-data','path':relative})
            except Exception as exc:
                result['unknown'].append({'component':'kiwix-data','path':relative,'reason':str(exc)})
        records['kiwix-data']=existing
    if result['adopted']:
        _path(root,'runtime/upgrades')
        (root/'runtime/upgrades').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='adopt-',dir=str(root/'runtime/upgrades')) as folder:
            staged=Path(folder)/'installation.json'
            staged.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
            result['transaction_id']=Transaction(root,'adopt').apply({'runtime/installation.json':str(staged)})
    return result
