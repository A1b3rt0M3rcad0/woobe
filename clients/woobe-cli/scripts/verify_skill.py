#!/usr/bin/env python3
"""Validate the immutable npm skill package and every portable reference."""
import argparse
import hashlib
import json
import pathlib
import re
import tarfile

from version import validate


def verify(root, record, version, commit):
    validate(version)
    assert record['name'] == f'woobe-cli-skill-{version}.tgz'
    artifact = root / record['name']
    assert artifact.stat().st_size == record['bytes']
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == record['sha256']
    with tarfile.open(artifact) as archive:
        entries = archive.getmembers()
        assert all(entry.isfile() for entry in entries), 'non-file npm skill entry'
        names = {entry.name for entry in entries}
        assert len(entries) == len(names), 'duplicate npm skill entry'
        source = pathlib.Path('packages/woobe-cli-skill')
        expected = {'package/package.json', 'package/README.md', 'package/bin/woobe-skill.cjs', 'package/lib/install.cjs'}
        expected |= {'package/' + file.relative_to(source).as_posix() for file in (source / 'skills').rglob('*') if file.is_file()}
        assert names == expected, 'unexpected npm skill contents'
        assert archive.extractfile('package/README.md').read() == pathlib.Path('docs/AGENT_SKILL.md').read_bytes(), 'skill README differs from reviewed guide'
        data = json.load(archive.extractfile('package/package.json'))
        assert data['name'] == 'woobe-cli-skill' and data['version'] == version
        assert data.get('private') is not True
        assert not data.get('scripts') and not data.get('dependencies') and not data.get('optionalDependencies')
        assert data['bin'] == {'woobe-skill': 'bin/woobe-skill.cjs'}
        assert data['woobeSkill']['sourceCommit'] == commit
        assert data['woobeSkill']['minimumCliVersion'] == '0.32.3'
        assert archive.getmember('package/bin/woobe-skill.cjs').mode & 0o111
        for file in source.rglob('*.cjs'):
            assert archive.extractfile('package/' + file.relative_to(source).as_posix()).read() == file.read_bytes()
        for file in (source / 'skills').rglob('*'):
            if not file.is_file():
                continue
            name = 'package/' + file.relative_to(source).as_posix()
            content = archive.extractfile(name).read()
            assert content == file.read_bytes(), 'skill differs from reviewed source'
            if file.suffix == '.md':
                for link in re.findall(r'\]\(([^)]+)\)', content.decode('utf-8')):
                    assert not link.startswith(('http:', 'https:')), 'skill references must be available offline'
                    resolved = (file.parent / link).resolve()
                    assert resolved.is_relative_to((source / 'skills/woobe-cli').resolve()) and resolved.is_file(), 'broken skill reference'
        text = archive.extractfile('package/skills/woobe-cli/SKILL.md').read().decode('utf-8')
        assert text.startswith('---\nname: woobe-cli\n')
        assert re.search(r'^description: .{20,1024}$', text, re.M)
        assert len(text.encode()) < 5000, 'main skill must remain small'
    return {'version': version, 'commit': commit, 'package': record['name'], 'success': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--version')
    options = parser.parse_args()
    root = pathlib.Path('dist')
    manifest = json.loads((root / 'artifacts.json').read_text())
    assert manifest['commit'] == options.commit
    assert not options.version or options.version == manifest['version']
    print(json.dumps(verify(root, manifest['skill_npm'], manifest['version'], options.commit)))
