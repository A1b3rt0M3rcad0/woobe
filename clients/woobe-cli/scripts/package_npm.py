#!/usr/bin/env python3
"""Pack the same six binaries into one npm package, without install scripts."""
import argparse
import json
import pathlib
import shutil
import subprocess

from version import check, validate


def package(version):
    check()
    validate(version)
    root = pathlib.Path('dist').resolve()
    stage = root / 'npm'
    manifest = stage / 'package.json'
    shutil.copytree('packages/woobe-cli', stage, dirs_exist_ok=True)
    shutil.copy2('docs/USAGE.md', stage / 'USAGE.md')
    shutil.copy2(root / 'THIRD_PARTY_NOTICES.txt', stage / 'THIRD_PARTY_NOTICES.txt')
    data = json.loads(manifest.read_text())
    data['version'] = version
    data.pop('private', None)
    manifest.write_text(json.dumps(data, indent=2) + '\n')
    npm = shutil.which('npm')
    if not npm:
        raise RuntimeError('npm is required to build the distribution package')
    result = subprocess.run([npm, 'pack', '--ignore-scripts', '--json', '--pack-destination', str(root)],
                            cwd=stage, check=True, capture_output=True, text=True)
    name = json.loads(result.stdout)[0]['filename']
    if name != f'woobe-cli-{version}.tgz':
        raise ValueError('unexpected npm artifact name')
    return name


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    print(package(parser.parse_args().version))
