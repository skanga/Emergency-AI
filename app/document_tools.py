"""Explicit, verified PDF-tool preparation; never called by answer generation."""

import json
import os
from pathlib import Path
import tempfile

from .config import platform_key
from .prepare import download, extract


def _artifact(platform):
    path = Path(__file__).resolve().parent.parent / 'config/document-tools.json'
    return json.loads(path.read_text())['supported_platforms'].get(platform)


def tool_status(root, platform=None):
    platform = platform or platform_key()
    artifact = _artifact(platform)
    if not artifact:
        return {'state': 'unsupported_platform', 'platform': platform}
    base = Path(root) / artifact['root']
    required = [artifact['binary'], artifact['pdfinfo'], 'README', 'COPYING', 'COPYING3', 'doc/pdftotext.1']
    if not all((base / name).is_file() for name in required):
        return {'state': 'extractor_missing', 'platform': platform, 'version': artifact['version']}
    return {'state': 'available', 'platform': platform, 'version': artifact['version'],
            'path': str((base / artifact['binary']).resolve())}


def prepare_tool(root, platform=None):
    platform = platform or platform_key()
    artifact = _artifact(platform)
    if not artifact:
        raise ValueError('unsupported_platform: ' + platform)
    state = tool_status(root, platform)
    if state['state'] == 'available':
        return state
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / artifact['url'].rsplit('/', 1)[-1]
    download(artifact['url'], str(archive), expected_size=artifact['size'], sha256=artifact['sha256'])
    with tempfile.TemporaryDirectory(dir=root) as staging:
        extract(str(archive), staging)
        state = tool_status(staging, platform)
        if state['state'] != 'available':
            raise RuntimeError('extractor_package_incomplete')
        destination = root / artifact['root']
        # A partially installed directory remains available for inspection;
        # never recursively delete a user-supplied tool directory.
        if destination.exists():
            raise RuntimeError('extractor_install_incomplete: move aside ' + str(destination))
        os.replace(Path(staging) / artifact['root'], destination)
    return tool_status(root, platform)
