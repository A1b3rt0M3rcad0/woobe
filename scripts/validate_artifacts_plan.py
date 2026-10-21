"""Read-only validation of the ordered, always-Draft Artifacts delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/implementation/artifacts'
STATUSES = {'not_started', 'in_progress', 'blocked', 'completed'}
OUTCOMES = {'passed', 'failed', 'not_run', 'skipped'}
PROTECTED = {
    '.github/workflows/release.yml',
    '.github/workflows/prepare-release.yml',
    '.github/workflows/release-candidate.yml',
}
ALLOWED_ROOT_FILES = {
    'go.work', 'go.work.sum', 'pyproject.toml', 'uv.lock', 'pytest.ini',
    'Dockerfile', 'compose.yaml', 'compose.test.yaml', '.env.example',
    '.gitignore', '.dockerignore', 'README.md', 'CHANGELOG.md',
    'THIRD_PARTY_NOTICES.md',
    'compose.artifacts-documents.yaml', 'compose.artifacts-pageindex.yaml',
}
ALLOWED_DIRS = {
    'packages', 'clients', 'contracts', 'docs', 'scripts', 'tests',
    'tooling', 'specs', 'deploy', 'docker', '.github',
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_manifest(manifest: dict, plan: bytes, *, final: bool = False) -> None:
    require(manifest.get('schema_version') == 1, 'Unsupported manifest schema')
    require(re.fullmatch(r'[0-9a-f]{40}', manifest.get('base_commit', '')) is not None,
            'Invalid immutable base SHA')
    require(hashlib.sha256(plan).hexdigest() == manifest.get('source_sha256'),
            'The supplied plan was changed without reconciling its provenance')
    steps = manifest.get('steps', [])
    require([step.get('id') for step in steps] == list(range(1, 61)),
            'Exactly 60 unique ordered step IDs are required')
    for step in steps:
        number = step['id']
        require(step.get('status') in STATUSES, f'Invalid step {number} status')
        dependencies = step.get('dependencies', [])
        require(all(isinstance(dep, int) and 0 < dep < number for dep in dependencies),
                f'Step {number} depends on a nonexistent or later step')
        require(len(dependencies) == len(set(dependencies)),
                f'Step {number} repeats a dependency')
        require(bool(step.get('commit_subject')), f'Step {number} has no subject')
        for check in step.get('checks', []):
            require(check.get('outcome') in OUTCOMES, f'Invalid outcome for {number}')
            require(bool(check.get('command')) and bool(check.get('evidence')),
                    f'Missing command/evidence for {number}')
        if step['status'] == 'completed':
            require(bool(step.get('checks')), f'Step {number} lacks evidence')
            require(any(check['outcome'] == 'passed' for check in step['checks']),
                    f'Step {number} has no passing validation')
            require(not any(check['outcome'] == 'failed' for check in step['checks']),
                    f'Step {number} has unresolved failed validation')
            require(all(steps[dep - 1]['status'] == 'completed' for dep in dependencies),
                    f'Step {number} has unfinished dependencies')
        if final:
            require(step['status'] == 'completed', f'Step {number} is unfinished')
    if final:
        require(manifest.get('pull_request', {}).get('draft') is True,
                'Final delivery must remain Draft')


def validate_event(event: dict, branch: str) -> None:
    pr = event.get('pull_request')
    require(isinstance(pr, dict), 'A real pull_request event is required')
    require(pr.get('draft') is True, 'The implementation PR must remain Draft')
    require(pr.get('state') == 'open' and not pr.get('merged', False),
            'The implementation PR must remain open and unmerged')
    require(pr.get('auto_merge') is None, 'Auto-merge is prohibited')
    require(pr.get('head', {}).get('ref') == branch, 'Unexpected feature branch')
    require(pr.get('base', {}).get('ref') == 'master', 'Unexpected target branch')


def validate_commits(commits: list[dict], steps: list[dict], *, final: bool = False) -> None:
    require(0 < len(commits) <= 60, 'Expected between 1 and 60 implementation commits')
    if final:
        require(len(commits) == 60, 'Final delivery requires exactly 60 commits')
    for number, commit in enumerate(commits, 1):
        require(len(commit['parents']) == 1, 'Merge commits are prohibited')
        require(commit['subject'] == steps[number - 1]['commit_subject'],
                f'Unexpected subject for step {number}')
        trailers = re.findall(r'^Plan-Step: (\d{2})/60$', commit['message'], re.M)
        require(trailers == [f'{number:02}'], f'Invalid step {number} trailer')
        require(bool(commit['files']), f'Empty step {number} commit')
        for filename in commit['files']:
            require(filename not in PROTECTED, 'Publication workflow changes are prohibited')
            path = Path(filename)
            require(filename in ALLOWED_ROOT_FILES or path.parts[0] in ALLOWED_DIRS,
                    f'Out-of-scope path: {filename}')
            require(not any(part in {'.git', '.state', 'node_modules', '.venv'}
                            for part in path.parts), f'Private/cache path: {filename}')
            require(path.name != '.env', 'Local environment secrets cannot be committed')


def git(*args: str) -> str:
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--event', type=Path)
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    try:
        manifest = json.loads((LEDGER / 'manifest.json').read_text())
        validate_manifest(manifest, (LEDGER / 'PLAN.md').read_bytes(), final=args.final)
        base = args.base or manifest['base_commit']
        require(git('rev-parse', f'{base}^{{commit}}') == manifest['base_commit'],
                'Base differs from the audited immutable baseline')
        subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', base,
                        args.head], check=True)
        if args.event:
            validate_event(json.loads(args.event.read_text()), manifest['branch'])
        implementation_head = args.head
        head_parents = git('show', '-s', '--format=%P', args.head).split()
        if len(head_parents) == 2:
            # The completed 60-step series may be followed by one integration
            # merge to resolve changes made to master after the audited base.
            implementation_head, upstream_head = head_parents
            require(git('rev-list', '--count', f'{base}..{implementation_head}') == '60',
                    'Integration merge must directly follow the completed plan')
            subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor',
                            base, upstream_head], check=True)
            require(git('merge-base', implementation_head, upstream_head) == base,
                    'Integration merge must join the original plan and upstream history')
        else:
            require(len(head_parents) == 1, 'Unexpected head commit parents')
        commits = []
        for sha in git('rev-list', '--reverse', f'{base}..{implementation_head}').splitlines():
            commits.append({
                'sha': sha,
                'parents': git('show', '-s', '--format=%P', sha).split(),
                'subject': git('show', '-s', '--format=%s', sha),
                'message': git('show', '-s', '--format=%B', sha),
                'files': git('diff-tree', '--no-commit-id', '--name-only', '-r', sha).splitlines(),
            })
        validate_commits(commits, manifest['steps'], final=args.final)
        print(json.dumps({'status': 'passed', 'final': args.final, 'commits': [
            {'step': i, 'sha': commit['sha']} for i, commit in enumerate(commits, 1)
        ]}, indent=2))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Artifacts plan guard: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
