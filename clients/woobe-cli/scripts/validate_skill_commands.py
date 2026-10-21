#!/usr/bin/env python3
"""Validate offline skill examples with CLI help; never execute their operations."""
import argparse
import pathlib
import shlex
import subprocess


def validate(binary):
    checked = []
    for file in pathlib.Path('packages/woobe-cli-skill/skills/woobe-cli').rglob('*.md'):
        fence = False
        for line in file.read_text().splitlines():
            if line.startswith('```'):
                fence = not fence
                continue
            if not fence or not line.startswith('woobe '):
                continue
            args = shlex.split(line)[1:]
            # Adding Cobra's help flag prevents handlers/body reads/server calls.
            result = subprocess.run([str(binary), *args, '--help'], capture_output=True, text=True, timeout=10)
            if result.returncode or 'unknown command' in result.stdout + result.stderr or 'unknown flag' in result.stdout + result.stderr:
                raise ValueError(f'{file}: invalid skill command: {line}: {result.stdout}{result.stderr}')
            checked.append(line)
    if len(checked) < 30:
        raise ValueError('unexpectedly few skill examples checked')
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=pathlib.Path)
    args = parser.parse_args()
    print(f'{len(validate(args.binary.resolve()))} offline skill command examples accepted')
