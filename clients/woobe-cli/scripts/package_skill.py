#!/usr/bin/env python3
"""Package the portable assistant skill without executing installation scripts."""
import argparse
import json
import pathlib
import re
import shutil
import subprocess

from version import check, validate


def package(version, commit):
    check()
    validate(version)
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('skill package requires an exact source commit')
    root = pathlib.Path('dist').resolve()
    stage = root / 'npm-skill'
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree('packages/woobe-cli-skill', stage, ignore=shutil.ignore_patterns('tests'))
    manifest = stage / 'package.json'
    data = json.loads(manifest.read_text())
    data['version'] = version
    data.pop('private', None)
    data['woobeSkill']['sourceCommit'] = commit
    manifest.write_text(json.dumps(data, indent=2) + '\n')
    shutil.copy2('docs/AGENT_SKILL.md', stage / 'README.md')
    result = subprocess.run(['npm', 'pack', '--ignore-scripts', '--json', '--pack-destination', str(root)],
                            cwd=stage, check=True, capture_output=True, text=True)
    name = json.loads(result.stdout)[0]['filename']
    if name != f'woobe-cli-skill-{version}.tgz':
        raise ValueError('unexpected skill npm artifact name')
    return name


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    parser.add_argument('--commit', required=True)
    options = parser.parse_args()
    print(package(options.version, options.commit))
