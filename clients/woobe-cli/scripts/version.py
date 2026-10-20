#!/usr/bin/env python3
"""Keep the independent source release floor and reserved npm metadata synchronized."""
import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / 'VERSION'
PACKAGE_FILE = ROOT / 'packages/woobe-cli/package.json'
SKILL_PACKAGE_FILE = ROOT / 'packages/woobe-cli-skill/package.json'
NUMBER = r'(?:0|[1-9][0-9]*)'
IDENTIFIER = rf'(?:{NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
SEMVER = re.compile(rf'{NUMBER}\.{NUMBER}\.{NUMBER}(?:-{IDENTIFIER}(?:\.{IDENTIFIER})*)?')


def validate(value):
    if not SEMVER.fullmatch(value):
        raise ValueError('expected X.Y.Z or X.Y.Z-prerelease (no v prefix or build metadata)')
    return value


def semver_key(value):
    validate(value)
    core, separator, prerelease = value.partition('-')
    identifiers = tuple((0, int(part)) if part.isdigit() else (1, part)
                        for part in prerelease.split('.')) if separator else ()
    return (*map(int, core.split('.')), 0 if separator else 1, identifiers)


def check():
    version = validate(VERSION_FILE.read_text().strip())
    package = json.loads(PACKAGE_FILE.read_text())
    if package['version'] != version:
        raise ValueError('npm package version differs from canonical VERSION')
    if json.loads(SKILL_PACKAGE_FILE.read_text())['version'] != version:
        raise ValueError('skill npm package version differs from canonical VERSION')
    return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--set', metavar='VERSION')
    action.add_argument('--validate', metavar='VERSION')
    options = parser.parse_args()
    try:
        if options.validate is not None:
            print(validate(options.validate))
        else:
            if options.set is not None:
                version = validate(options.set)
                package = json.loads(PACKAGE_FILE.read_text())
                package['version'] = version
                VERSION_FILE.write_text(version + '\n')
                PACKAGE_FILE.write_text(json.dumps(package, indent=2) + '\n')
                skill = json.loads(SKILL_PACKAGE_FILE.read_text())
                skill['version'] = version
                SKILL_PACKAGE_FILE.write_text(json.dumps(skill, indent=2) + '\n')
            print(check())
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, f'CLI version: {error}\n')
