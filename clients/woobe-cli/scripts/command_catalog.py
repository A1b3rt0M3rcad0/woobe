#!/usr/bin/env python3
"""Render the current executable catalog from read-only CLI discovery."""
import argparse
import json
import pathlib
import subprocess


def render(binary):
    result = subprocess.run([str(binary), 'help', '--output', 'json'], check=True, capture_output=True, text=True)
    entries = json.loads(result.stdout)['data']
    http_count = sum(entry['kind'] == 'http' for entry in entries)
    lines = ['# Executable command catalog', '',
             f'Generated from current discovery: {len(entries)} executable entries, including {http_count} HTTP operations. Route advertisement does not grant authority. See [USAGE.md](USAGE.md) for workflows, [PAGINATION.md](PAGINATION.md) for reviewed pagination and [AGENT_SKILL.md](AGENT_SKILL.md) for embedded assistant skill setup.', '',
             'Regenerate with `python3 scripts/command_catalog.py --binary bin/woobe --write`. Assistant installation uses local `skills` commands, not HTTP operations. The optional npm `woobe-skill` executable uses the same payload and receipts.', '',
             '| Command | Kind | HTTP | Availability | Permission hint | Pagination |',
             '| --- | --- | --- | --- | --- | --- |']
    for entry in entries:
        route = f"{entry['method']} {entry['path']}" if entry['kind'] == 'http' else '—'
        pagination = entry.get('pagination', {})
        values = [f"`{entry['command']}`", f"`{entry['kind']}`", f'`{route}`' if route != '—' else route,
                  f"`{entry['availability']}`", entry.get('permission') or '—',
                  pagination.get('protocol', '—') if isinstance(pagination, dict) else str(pagination)]
        lines.append('| ' + ' | '.join(str(value).replace('|', '\\|') for value in values) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=pathlib.Path, required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    expected = render(args.binary.resolve())
    document = pathlib.Path('docs/OPERATIONS.md')
    if args.write:
        document.write_text(expected)
    else:
        assert document.read_text() == expected, 'regenerate docs/OPERATIONS.md'
