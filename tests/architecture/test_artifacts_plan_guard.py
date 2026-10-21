"""Guard behavior: malformed delivery must fail without changing GitHub state."""

from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'artifacts_guard', ROOT / 'scripts/validate_artifacts_plan.py'
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def manifest():
    return {
        'schema_version': 1,
        'source_sha256': hashlib.sha256(b'plan').hexdigest(),
        'base_commit': 'a' * 40,
        'steps': [{
            'id': number, 'dependencies': [number - 1] if number > 1 else [],
            'status': 'not_started', 'checks': [], 'commit_subject': f'step {number}',
        } for number in range(1, 61)],
    }


def commit(number):
    return {'parents': ['parent'], 'files': ['docs/implementation/artifacts/PROGRESS.md'],
            'subject': f'step {number}', 'message': f'step {number}\n\nPlan-Step: {number:02}/60'}


def test_manifest_has_sixty_ordered_unique_steps_and_audited_plan():
    guard.validate_manifest(manifest(), b'plan')
    data = manifest()
    data['steps'][20]['id'] = 20
    with pytest.raises(ValueError, match='unique ordered'):
        guard.validate_manifest(data, b'plan')
    with pytest.raises(ValueError, match='provenance'):
        guard.validate_manifest(manifest(), b'modified plan')


def test_completion_requires_passing_evidence_and_completed_dependencies():
    data = manifest()
    data['steps'][1]['status'] = 'completed'
    with pytest.raises(ValueError, match='evidence'):
        guard.validate_manifest(data, b'plan')
    data['steps'][1]['checks'] = [
        {'command': 'pytest actual-selection', 'outcome': 'passed', 'evidence': '2 passed'},
    ]
    with pytest.raises(ValueError, match='unfinished dependencies'):
        guard.validate_manifest(data, b'plan')
    data['steps'][0] = deepcopy(data['steps'][1]) | {'id': 1, 'dependencies': []}
    guard.validate_manifest(data, b'plan')


def test_partial_progress_is_valid_but_not_final():
    guard.validate_commits([commit(1)], manifest()['steps'])
    with pytest.raises(ValueError, match='exactly 60'):
        guard.validate_commits([commit(1)], manifest()['steps'], final=True)
    with pytest.raises(ValueError, match='unfinished'):
        guard.validate_manifest(manifest(), b'plan', final=True)


@pytest.mark.parametrize('change,reason', [
    ({'parents': ['a', 'b']}, 'Merge'),
    ({'files': []}, 'Empty'),
    ({'message': 'Plan-Step: 02/60'}, 'trailer'),
    ({'message': 'Plan-Step: 01/60\nPlan-Step: 01/60'}, 'trailer'),
    ({'subject': 'unplanned fix'}, 'subject'),
    ({'files': ['.github/workflows/release.yml']}, 'Publication'),
    ({'files': ['packages/app/.env']}, 'secrets'),
    ({'files': ['clients/woobe-cli/.state/credentials.json']}, 'Private/cache'),
    ({'files': ['unrelated.txt']}, 'Out-of-scope'),
])
def test_invalid_series_is_rejected(change, reason):
    with pytest.raises(ValueError, match=reason):
        guard.validate_commits([commit(1) | change], manifest()['steps'])


def test_only_open_draft_without_auto_merge_is_accepted():
    pr = {'draft': True, 'state': 'open', 'merged': False, 'auto_merge': None,
          'head': {'ref': 'feature'}, 'base': {'ref': 'master'}}
    guard.validate_event({'pull_request': pr}, 'feature')
    for changes in [
        {'draft': False}, {'state': 'closed'}, {'merged': True}, {'auto_merge': {}},
        {'head': {'ref': 'other'}}, {'base': {'ref': 'other'}},
    ]:
        with pytest.raises(ValueError):
            guard.validate_event({'pull_request': pr | changes}, 'feature')
    with pytest.raises(ValueError, match='real pull_request'):
        guard.validate_event({}, 'feature')


def test_sixty_commits_do_not_accept_reordering_or_a_sixty_first_commit():
    commits = [commit(number) for number in range(1, 61)]
    guard.validate_commits(commits, manifest()['steps'], final=True)
    with pytest.raises(ValueError):
        guard.validate_commits(commits + [commit(61)], manifest()['steps'])
    commits[10], commits[11] = commits[11], commits[10]
    with pytest.raises(ValueError):
        guard.validate_commits(commits, manifest()['steps'])
