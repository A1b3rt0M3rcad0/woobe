#!/usr/bin/env python3
"""Prepare an OCI context from the exact validated Linux archive binaries."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile


def prepare(commit, version, digest, epoch=0):
    root = pathlib.Path('dist')
    metadata = root / 'artifacts.json'
    if hashlib.sha256(metadata.read_bytes()).hexdigest() != digest:
        raise ValueError('candidate manifest digest differs from successful CI')
    manifest = json.loads(metadata.read_text())
    if manifest['commit'] != commit or manifest['version'] != version:
        raise ValueError('container source must match the exact validated candidate')
    subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('verify_artifacts.py')),
                    '--commit', commit, '--version', version], check=True)
    context = root / 'oci'
    if context.exists():
        shutil.rmtree(context)
    (context / 'data').mkdir(parents=True)
    (context / 'data/.keep').write_text('')
    for arch in ('amd64', 'arm64'):
        artifact = next(a for a in manifest['artifacts'] if a['os'] == 'linux' and a['arch'] == arch)
        with tarfile.open(root / artifact['name']) as archive:
            member = archive.getmember('woobe')
            if not member.isfile() or member.size > 80 * 1024 * 1024:
                raise ValueError('unexpected native executable')
            binary = archive.extractfile(member).read()
        target = context / arch / 'woobe'
        target.parent.mkdir()
        target.write_bytes(binary)
        target.chmod(0o755)
    for path in context.rglob('*'):
        os.utime(path, (epoch, epoch))
    os.utime(context, (epoch, epoch))
    return context


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    epoch = int(subprocess.check_output(['git', 'show', '-s', '--format=%ct', args.commit], text=True).strip())
    print(prepare(args.commit, args.version, args.manifest_sha256, epoch))
