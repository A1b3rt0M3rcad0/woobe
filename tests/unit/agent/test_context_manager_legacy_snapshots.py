from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from modules.agent.application.context_manager_registry import (
    canonicalize_context_manager_runtime_config,
)
from modules.agent.application.dtos.ai_dtos import UpdateAgentInput
from modules.agent.application.execution_snapshot import (
    apply_agent_execution_snapshot,
    build_agent_execution_snapshot,
)
from modules.agent.application.interfaces.context_manager import (
    context_manager_key_from_runtime_config,
)
from modules.agent.application.use_cases.ai_agent_cases import UpdateAgentUseCase
from modules.agent.domain.entities import Agent, AgentRelease
from modules.agent.domain.enums import Provider, ReleaseStatus


def legacy_selection(version='v1'):
    return {'name': 'default', 'version': version, 'strategy_name': 'stdcm', 'strategy_version': version}


@pytest.mark.parametrize('field', ['context_assembler', 'context_manager'])
@pytest.mark.parametrize('version', ['v1', 'v2'])
@pytest.mark.parametrize('explicit', [False, True])
def test_legacy_selection_is_read_without_mutation_and_written_name_only(field, version, explicit):
    selection = legacy_selection(version)
    if explicit:
        selection['name'] = 'stdcm'
    runtime = {field: selection, 'tools': {'tool_ids': ['tool-1']}, 'context_policy': {'budget': 1000}}
    before = deepcopy(runtime)
    assert context_manager_key_from_runtime_config(runtime).name == 'stdcm'
    canonical = canonicalize_context_manager_runtime_config(runtime)
    assert canonical == {**{k: v for k, v in runtime.items() if k != field}, 'context_manager': {'name': 'stdcm'}}
    assert runtime == before
    assert canonical['tools'] is not runtime['tools']


@pytest.mark.parametrize('version', ['v1', 'v2'])
def test_old_snapshot_without_frozen_strategy_is_supported(version):
    assert context_manager_key_from_runtime_config({
        'context_assembler': {'name': 'default', 'version': version},
    }).name == 'stdcm'


@pytest.mark.parametrize('selection', [
    {'name': 'stdcm', 'version': 'v999'},
    {'name': 'custom', 'version': 'v1'},
    {'name': 'default', 'version': 'v1', 'strategy_name': 'custom', 'strategy_version': 'v1'},
    {'name': 'stdcm', 'version': 'v1', 'strategy_name': 'stdcm', 'strategy_version': 'v2'},
    {'name': 'default', 'version': 'v1', 'strategy_name': 'stdcm'},
    {'name': 'default', 'version': 'v1', 'strategy_version': 'v1'},
    {'name': 'default', 'version': 1},
    {'name': 'stdcm', 'strategy_name': 'stdcm', 'strategy_version': 'v1'},
    {'name': 'stdcm', 'version': 'v1', 'typo': True},
])
def test_unknown_or_contradictory_legacy_schema_is_rejected(selection):
    with pytest.raises(ValueError):
        context_manager_key_from_runtime_config({'context_assembler': selection})


def test_conflicting_current_and_legacy_selections_are_rejected():
    with pytest.raises(ValueError, match='conflicting'):
        context_manager_key_from_runtime_config({
            'context_manager': {'name': 'custom'}, 'context_assembler': legacy_selection(),
        })


def test_playground_snapshot_override_reads_legacy_selection_without_mutating_input():
    from modules.agent.infra.execution.release_runtime_resolver import (
        ReleaseRuntimeResolver,
    )

    runtime = {'context_assembler': legacy_selection()}
    before = deepcopy(runtime)
    agent = Agent(project_id=uuid4(), provider=Provider.custom, model='test-model')
    prepared = ReleaseRuntimeResolver._apply_runtime_config_snapshot(agent, runtime)
    assert context_manager_key_from_runtime_config(prepared.settings['runtime_config']).name == 'stdcm'
    assert runtime == before


@pytest.mark.parametrize('status', [ReleaseStatus.staging, ReleaseStatus.production])
def test_release_snapshot_can_execute_without_rewriting_frozen_configuration(status):
    runtime = {'context_assembler': legacy_selection()}
    release = AgentRelease(
        project_id=uuid4(), agent_id=uuid4(), version='1.0.0', status=status,
        provider='custom', model='test-model', session_mode='stateful', runtime_config=deepcopy(runtime),
    )
    snapshot = build_agent_execution_snapshot(release)
    frozen = deepcopy(snapshot)
    target = Agent(project_id=release.project_id, provider=Provider.custom, model='test-model')
    apply_agent_execution_snapshot(target, snapshot)
    assert context_manager_key_from_runtime_config(target.settings['runtime_config']).name == 'stdcm'
    assert release.runtime_config == runtime
    assert snapshot == frozen


@pytest.mark.asyncio
async def test_saving_existing_agent_upgrades_legacy_selection():
    agent = Agent(project_id=uuid4(), provider=Provider.custom, model='test-model',
                  settings={'runtime_config': {'context_assembler': legacy_selection()}})
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=agent), update=AsyncMock(side_effect=lambda value: value))
    use_case = UpdateAgentUseCase(repository, SimpleNamespace(), SimpleNamespace(write=AsyncMock()))
    await use_case.execute(agent.id, UpdateAgentInput(name='Updated agent'))
    saved = repository.update.call_args.args[0]
    assert saved.settings['runtime_config']['context_manager'] == {'name': 'stdcm'}
    assert 'context_assembler' not in saved.settings['runtime_config']
