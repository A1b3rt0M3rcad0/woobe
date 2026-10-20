import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess

from modules.artifacts.domain.models import ArtifactError


RECEIPT = '.woobe-tesseract-receipt.json'


def read_ocr_manifest():
    content = files('modules.artifacts.infra.processing').joinpath('manifests/tesseract-fast-v1.json').read_bytes()
    return json.loads(content), hashlib.sha256(content).hexdigest()


def file_identity(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(65_536), b''):
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'size_bytes': path.stat().st_size}


def qualify_installation(directory, executable):
    root, binary = Path(directory).resolve(), Path(executable).resolve()
    manifest, digest = read_ocr_manifest()
    if not Path(executable).is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'OCR executable is unavailable')
    result = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=5, check=False)
    lines = result.stdout.splitlines()
    if result.returncode != 0 or not lines or lines[0].strip() != 'tesseract ' + manifest['engine_version']:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'OCR engine version differs from its qualified manifest')
    identities = {}
    for entry in manifest['models'][0]['files']:
        path = root / entry['path']
        if path.is_symlink() or not path.is_file() or path.stat().st_size != entry['size_bytes']:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'OCR language or orientation model is unavailable')
        identity = file_identity(path)
        if identity['sha256'] != entry['sha256']:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'OCR model differs from its pinned upstream artifact')
        identities[entry['path']] = identity
    return {'schema_version': '1', 'manifest_sha256': digest, 'engine_version': manifest['engine_version'],
            'executable': str(binary), 'executable_identity': file_identity(binary),
            'engine_build_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(), 'files': identities}


def ocr_readiness(directory, executable):
    manifest, digest = read_ocr_manifest()
    if directory is None:
        return False, 'ocr_models_not_configured', None, manifest, digest
    try:
        root = Path(directory).resolve()
        receipt_path = root / RECEIPT
        if receipt_path.stat().st_size > 16_384:
            raise ValueError('Invalid OCR installation receipt')
        receipt = json.loads(receipt_path.read_bytes())
        if receipt['manifest_sha256'] != digest or receipt['engine_version'] != manifest['engine_version'] or receipt['executable'] != str(Path(executable).resolve()):
            raise ValueError('OCR installation receipt does not match configuration')
        paths = [(Path(receipt['executable']), receipt['executable_identity'])]
        paths.extend((root / name, identity) for name, identity in receipt['files'].items())
        if set(receipt['files']) != {entry['path'] for entry in manifest['models'][0]['files']}:
            raise ValueError('OCR installation receipt is incomplete')
        for path, identity in paths:
            if path.is_symlink() or not path.is_file() or file_identity(path) != identity:
                raise ValueError('OCR installed artifact changed after qualification')
        return True, '', receipt, manifest, digest
    except (OSError, KeyError, TypeError, ValueError):
        return False, 'ocr_installation_not_verified', None, manifest, digest
