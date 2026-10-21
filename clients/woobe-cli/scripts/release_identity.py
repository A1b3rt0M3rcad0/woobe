#!/usr/bin/env python3
"""Choose an automatic immutable CLI version without writing or merging source."""
import argparse
import json
import pathlib
import re
import subprocess
from version import validate, semver_key


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def ancestor(older, newer):
    result = subprocess.run(['git', 'merge-base', '--is-ancestor', older, newer])
    if result.returncode not in (0, 1):
        raise RuntimeError('cannot determine release ancestry')
    return result.returncode == 0


def source_floor(sha):
    floor = validate(git('show', f'{sha}:VERSION'))
    manifest = json.loads(git('show', f'{sha}:packages/woobe-cli/package.json'))
    if manifest['version'] != floor:
        raise ValueError('source VERSION and reserved npm manifest differ')
    return floor


def tags():
    versions = {}
    for tag in git('tag', '--list', 'v*').splitlines():
        try:
            version = validate(tag[1:])
        except ValueError:
            continue
        versions[version] = git('rev-parse', f'refs/tags/{tag}^{{commit}}')
    return versions


def bump(version, messages):
    major, minor, patch = map(int, version.split('-')[0].split('.'))
    commits = [message.strip() for message in messages.split('\0') if message.strip()]
    breaking = any(re.match(r'^[A-Za-z][A-Za-z0-9_-]*(?:\([^\n)]+\))?!:', message)
                   or re.search(r'(?m)^BREAKING[ -]CHANGE:', message) for message in commits)
    feature = any(re.match(r'^feat(?:\([^\n)]+\))?:', message) for message in commits)
    if breaking and major > 0:
        return f'{major + 1}.0.0'
    if breaking or feature:
        return f'{major}.{minor + 1}.0'
    if '-' in version:
        return f'{major}.{minor}.{patch}'
    return f'{major}.{minor}.{patch + 1}'


def select(version='', revision='', trusted_tag=False):
    if revision and not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('revision must be a full lowercase commit SHA')
    if version:
        validate(version)
    versions = tags()
    sha = revision or versions.get(version) or git('rev-parse', 'HEAD')
    if trusted_tag and versions.get(version) != sha:
        raise ValueError('tagged publication must match an existing immutable source tag')
    if not trusted_tag and not ancestor(sha, 'origin/master'):
        raise ValueError('release source must already be integrated in master')
    floor = source_floor(sha)
    if version in versions:
        if versions[version] != sha:
            raise ValueError('existing immutable tag points to a different commit')
        if semver_key(version) < semver_key(floor):
            raise ValueError('release version is below the reviewed source VERSION floor')
        return version, sha
    if not version:
        matching = [v for v, commit in versions.items() if commit == sha and semver_key(v) >= semver_key(floor)]
        if matching:
            return max(matching, key=semver_key), sha
    if versions:
        latest = max(versions, key=semver_key)
        previous = versions[latest]
        if not ancestor(previous, sha):
            if version:
                raise ValueError('new release source predates the latest reserved release')
            return None  # A newer source already has a version; skip stale push.
        if version and semver_key(version) <= semver_key(latest):
            raise ValueError('new releases must advance the highest reserved Semantic Version')
        if not version:
            messages = git('log', '--format=%B%x00', f'{previous}..{sha}')
            proposed = bump(latest, messages)
            version = max((floor, proposed), key=semver_key)
    else:
        version = version or floor
    if semver_key(version) < semver_key(floor):
        raise ValueError('release version is below the reviewed source VERSION floor')
    return version, sha


def resolve(version, revision, trusted_tag=False):
    selected = select(version, revision, trusted_tag)
    if selected != (version, revision):
        raise ValueError('candidate does not match the immutable release identity')
    return revision


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='')
    parser.add_argument('--revision', default='')
    parser.add_argument('--tag', default='')
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.tag:
        tagged_version = validate(args.tag[1:])
        if args.tag != 'v' + tagged_version or (args.version and args.version != tagged_version):
            parser.error('source tag and requested version differ')
        args.version = tagged_version
    selected = select(args.version, args.revision, bool(args.tag))
    with args.output.open('a') as output:
        if selected is None:
            output.write('skip=true\n')
            print('Skipping stale push: a newer source already has a release version')
        else:
            version, sha = selected
            output.write(f'version={version}\nrevision={sha}\nskip=false\n')
            print(f'Release v{version} will validate exact source revision {sha}')
