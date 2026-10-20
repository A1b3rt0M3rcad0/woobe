"""Inspect and promote a validated multi-platform GHCR CLI package."""
import json
import re
import subprocess


def inspect(ref, missing=False):
    result = subprocess.run(['docker', 'buildx', 'imagetools', 'inspect', ref], text=True, capture_output=True)
    if result.returncode:
        if missing and re.search(r'manifest unknown|manifest_unknown|404 Not Found|:\s*not found', result.stderr, re.I):
            return None
        raise RuntimeError(f'Cannot inspect registry target {ref}: {result.stderr}')
    match = re.search(r'^Digest:\s*(sha256:[a-f0-9]{64})\s*$', result.stdout, re.M)
    if not match:
        raise ValueError('registry inspection returned no immutable digest')
    return match.group(1)


def preflight(image, version, digest):
    if not re.fullmatch(r'ghcr\.io/[a-z0-9_.-]+/woobe-cli', image) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ValueError('invalid validated GHCR package identity')
    if inspect(image + '@' + digest) != digest:
        raise ValueError('candidate registry digest changed')
    raw = subprocess.check_output(['docker', 'buildx', 'imagetools', 'inspect', image + '@' + digest, '--raw'], text=True)
    manifest = json.loads(raw)
    platforms = {(m['platform']['os'], m['platform']['architecture']) for m in manifest.get('manifests', [])}
    if platforms != {('linux', 'amd64'), ('linux', 'arm64')}:
        raise ValueError('container package must contain exactly Linux amd64 and arm64')
    existing = inspect(image + ':' + version, missing=True)
    if existing is not None and existing != digest:
        raise ValueError('immutable GHCR version exists with a different digest')
    return existing is not None


def promote(image, tag, digest):
    subprocess.run(['docker', 'buildx', 'imagetools', 'create', '--tag', image + ':' + tag, image + '@' + digest], check=True)
    if inspect(image + ':' + tag) != digest:
        raise ValueError('promoted registry tag differs from validated digest')
