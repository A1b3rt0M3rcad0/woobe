#!/usr/bin/env python3
"""Describe exactly the six archives for this release version, without stale files."""
import hashlib, json, pathlib, sys
version, commit, compiler, with_npm = sys.argv[1:]
artifacts = []
for system in ('linux', 'darwin', 'windows'):
    for arch in ('amd64', 'arm64'):
        suffix = 'zip' if system == 'windows' else 'tar.gz'
        path = pathlib.Path('dist') / f'woobe_{version}_{system}_{arch}.{suffix}'
        artifacts.append(dict(name=path.name, os=system, arch=arch,
                              bytes=path.stat().st_size,
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
manifest = dict(
    schema_version='1', version=version, commit=commit, compiler=compiler,
    artifacts=artifacts)
if with_npm == '--with-npm':
    npm_path = pathlib.Path('dist') / f'woobe-cli-{version}.tgz'
    manifest['npm'] = dict(name=npm_path.name, bytes=npm_path.stat().st_size,
                          sha256=hashlib.sha256(npm_path.read_bytes()).hexdigest())
    skill_path = pathlib.Path('dist') / f'woobe-cli-skill-{version}.tgz'
    manifest['skill_npm'] = dict(name=skill_path.name, bytes=skill_path.stat().st_size,
                                sha256=hashlib.sha256(skill_path.read_bytes()).hexdigest())
pathlib.Path('dist/artifacts.json').write_text(json.dumps(manifest, indent=2) + '\n')
