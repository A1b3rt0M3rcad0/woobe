"""Explicit, hash-pinned model acquisition; never called during conversion.

The shipped docling-native manifest has no model files. A future model profile
requires an audited manifest with immutable upstream revisions, licenses, file
sizes and SHA-256 digests before this tool will download any weights.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


HOSTS = frozenset({'huggingface.co', 'cdn-lfs.hf.co', 'cdn-lfs-us-1.hf.co', 'cas-bridge.xethub.hf.co',
                   'raw.githubusercontent.com', 'github.com', 'release-assets.githubusercontent.com'})


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise ValueError('Model downloads require an approved HTTPS upstream')


class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        validate_url(new_url)
        return super().redirect_request(request, file, code, message, headers, new_url)


def model_files(manifest):
    models = manifest.get('models')
    if manifest.get('schema_version') != '1' or not isinstance(models, list) or len(models) > 8:
        raise ValueError('Invalid model acquisition manifest')
    entries, total, paths = [], 0, set()
    for model in models:
        if not re.fullmatch(r'[0-9a-f]{40}', model.get('revision', '')) or not model.get('license') or not model.get('model_id'):
            raise ValueError('Models need an immutable upstream revision and audited license')
        for entry in model.get('files', ()):
            path = PurePosixPath(entry['path'])
            size, digest = entry['size_bytes'], entry['sha256']
            if (not path.parts or path.is_absolute() or any(part in {'', '.', '..'} for part in entry['path'].split('/'))
                or '\\' in entry['path'] or entry['path'] in paths):
                raise ValueError('Invalid or duplicate model artifact path')
            if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= 2_147_483_648 or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('Model files need bounded size and SHA-256')
            validate_url(entry['url'])
            if model['revision'] not in urlsplit(entry['url']).path:
                raise ValueError('Model URL must pin its declared upstream revision')
            total += size
            if total > 4_294_967_296 or len(entries) >= 256:
                raise ValueError('Model manifest exceeds its acquisition budget')
            entries.append(entry)
            paths.add(entry['path'])
    return entries


def verified(path, entry):
    if not path.is_file() or path.is_symlink() or path.stat().st_size != entry['size_bytes']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(65_536), b''):
            digest.update(chunk)
    return digest.hexdigest() == entry['sha256']


def acquire(manifest, destination, *, download=False, opener=None):
    entries = model_files(manifest)
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError('Model destination cannot be a symlink')
    root = destination.resolve()
    opener = opener or build_opener(RestrictedRedirect())
    for entry in entries:
        path = root.joinpath(*PurePosixPath(entry['path']).parts)
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in (path, *path.parents) if p != root):
            raise ValueError('Model artifact path escapes its private destination')
        if verified(path, entry):
            continue
        if path.exists() or not download:
            raise ValueError('Pinned model artifact is missing or fails integrity verification')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.model-', delete=False) as output:
                temporary = Path(output.name)
                digest, size = hashlib.sha256(), 0
                with opener.open(Request(entry['url'], headers={'User-Agent': 'woobe-model-acquisition/1'}), timeout=30) as response:
                    while chunk := response.read(65_536):
                        size += len(chunk)
                        if size > entry['size_bytes']:
                            raise ValueError('Model download exceeds its pinned byte size')
                        digest.update(chunk)
                        output.write(chunk)
                if size != entry['size_bytes'] or digest.hexdigest() != entry['sha256']:
                    raise ValueError('Model download failed pinned integrity verification')
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return len(entries)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--download', action='store_true', help='Explicitly acquire missing pinned files; default verifies offline')
    args = parser.parse_args()
    if args.manifest.stat().st_size > 1_048_576:
        raise SystemExit('Model manifest exceeds its byte limit')
    manifest = json.loads(args.manifest.read_bytes())
    count = acquire(manifest, args.destination, download=args.download)
    print(f'Verified {count} pinned model files; no model is acquired implicitly by conversion')
