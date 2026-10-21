#!/usr/bin/env python3
"""Publish the tested npm tarball; refuse replacement and latest rollback."""
import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
import time

from version import semver_key, validate

REGISTRY = 'https://registry.npmjs.org/'


def wait_for_integrity(spec, expected, timeout=900):
    deadline = time.monotonic() + timeout
    while True:
        observed = view(spec, 'dist.integrity')
        if observed is not None:
            if observed != expected:
                raise ValueError('published npm bytes differ from validated candidate')
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('npm accepted publication, but the version is still processing; '
                               'retry the failed job after the registry exposes this version')
        print(f'{spec}: npm is still processing publication; waiting for registry visibility', flush=True)
        time.sleep(min(5, remaining))


def view(spec, field):
    result = subprocess.run(['npm', 'view', spec, field, '--json', '--registry', REGISTRY],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        try:
            error = json.loads(result.stdout or result.stderr)
        except ValueError:
            raise RuntimeError('npm registry lookup failed') from None
        if error.get('error', {}).get('code') == 'E404':
            return None
        raise RuntimeError('npm registry lookup failed; check registry access')
    return json.loads(result.stdout) if result.stdout.strip() else None


def publish(commit, version, manifest_sha256, package_name='woobe-cli'):
    if package_name not in ('woobe-cli', 'woobe-cli-skill'):
        raise ValueError('unsupported npm package')
    validate(version)
    root = pathlib.Path('dist')
    metadata = root / 'artifacts.json'
    if hashlib.sha256(metadata.read_bytes()).hexdigest() != manifest_sha256:
        raise ValueError('candidate manifest differs from successful CI')
    manifest = json.loads(metadata.read_text())
    if manifest['commit'] != commit or manifest['version'] != version:
        raise ValueError('npm source differs from validated release identity')
    subprocess.run([sys.executable, 'scripts/verify_artifacts.py', '--commit', commit,
                    '--version', version], check=True)
    # npm treats bare "dist/file.tgz" as a GitHub shorthand, not a file.
    record = manifest['skill_npm' if package_name == 'woobe-cli-skill' else 'npm']
    if record['name'] != f'{package_name}-{version}.tgz':
        raise ValueError('npm package filename differs from selected package')
    artifact = (root / record['name']).resolve()
    integrity = 'sha512-' + base64.b64encode(hashlib.sha512(artifact.read_bytes()).digest()).decode()
    spec = f'{package_name}@{version}'
    existing = view(spec, 'dist.integrity')
    if existing is not None:
        if existing != integrity:
            raise ValueError('immutable npm version already contains different bytes')
        print(f'{spec} already published with identical bytes; no changes')
        return
    latest = view(f'{package_name}@latest', 'version')
    # Explicit recovery of an older version must never move latest backwards.
    tag = 'next' if '-' in version else 'latest'
    if latest and tag == 'latest' and semver_key(version) <= semver_key(latest):
        tag = 'historical'
    subprocess.run(['npm', 'publish', str(artifact), '--access', 'public', '--provenance',
                    '--tag', tag, '--registry', REGISTRY], check=True, timeout=180)
    wait_for_integrity(spec, integrity)
    print(f'Published {spec} with tag {tag}; registry integrity verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--package', choices=['woobe-cli', 'woobe-cli-skill'], default='woobe-cli')
    options = parser.parse_args()
    publish(options.commit, options.version, options.manifest_sha256, options.package)
