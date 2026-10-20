import hashlib
from importlib.resources import files
import json

from modules.artifacts.infra.processing.readiness import probe_distribution


def read_docling_manifest():
    content = files('modules.artifacts.infra.processing').joinpath('manifests/docling-native-v1.json').read_bytes()
    value = json.loads(content)
    if (value['schema_version'] != '1' or value['profile'] != 'docling-native'
        or value['models'] or value['network_during_conversion'] or value['external_plugins'] or value['external_programs']):
        raise ValueError('Invalid offline native Docling manifest')
    return value, hashlib.sha256(content).hexdigest()


def docling_readiness():
    manifest, digest = read_docling_manifest()
    for name, expected in manifest['libraries'].items():
        available, diagnostic = probe_distribution(name, expected)
        if not available:
            return False, f'{name}:{diagnostic}', manifest, digest
    return True, '', manifest, digest
