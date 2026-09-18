from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.infra.context_management.managers.resolver import build_runtime_context_assembler
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.application.skill_bindings import freeze_skill_bindings, frozen_enabled_skills
from modules.agent.application.skill_packages import ImportSkillInput, parse_skill_package
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.domain.skills import SkillVersion, skill_package_hash
from modules.agent.infra.execution import transaction_bounded_structured_output as preparation
from modules.agent.infra.execution.explicit_runtime_persistence import ExplicitRuntimePersistenceMixin
from modules.agent.infra.execution.frozen_snapshot_runtime import FrozenSnapshotStructuredOutputRuntime
from modules.agent.infra.execution.instrumented_execution_runner import configure_skill_runtime, run_instrumented_execution
from modules.agent.infra.execution.runtime_preparation import configure_skill_binding_freezer

INSTRUCTION = 'Return exactly SKILL_CONTEXT_REACHED_MODEL for this controlled test.'


class _Transactions:
    def __init__(self, version):
        self.read_count = 0
        self.repositories = SimpleNamespace(
            provider_credentials=object(),
            skills=SimpleNamespace(get_version=AsyncMock(return_value=version)),
        )

    async def read(self, operation):
        self.read_count += 1
        return await operation(self.repositories, object())

    async def run(self, operation):
        raise AssertionError('Deferred preparation must not introduce a SQL write')


class _Runtime(FrozenSnapshotStructuredOutputRuntime):
    def __init__(self, agent, transactions):
        self.agent = agent
        super().__init__(transactions=transactions, llm_factory=object(), encryption_key='fixture')

    async def _load_agent(self, *_args): return self.agent
    async def _load_credential(self, *_args): return SimpleNamespace(metadata={})
    def _decrypt_api_key(self, *_args): return 'fixture'
    def _resolve_base_url(self, *_args): return None
    def _get_response_format(self, *_args): return {'enabled': False}
    async def _load_rag_context(self, *_args): return None, []

    def _build_messages(self, agent, rag, history, message, response_format):
        return [SystemMessage(content='Follow installed procedures.'), *history, HumanMessage(content=message)]


class _Model:
    def __init__(self, version_id):
        self.version_id = version_id
        self.received = []
        self.bound_names = None

    def bind_tools(self, tools, *, tool_choice):
        assert tool_choice == 'auto'
        names = {item['function']['name'] for item in tools}
        assert names == {'skills_activate', 'skills_read_resource'}
        self.bound_names = names

        async def invoke(messages, **kwargs):
            self.received.append(messages)
            materialized = any(INSTRUCTION in str(message.content) for message in messages)
            if not materialized:
                return AIMessage(content='', tool_calls=[{
                    'name': 'skills_activate',
                    'args': {'skill_version_id': str(self.version_id)},
                    'id': 'activate-skill',
                    'type': 'tool_call',
                }])
            return AIMessage(content='SKILL_CONTEXT_REACHED_MODEL')

        return SimpleNamespace(ainvoke=invoke)


@pytest.mark.asyncio
@pytest.mark.parametrize('network', [False, True], ids=['standalone', 'network'])
async def test_skill_instructions_cross_real_preparation_and_registry(monkeypatch, network):
    package = parse_skill_package(ImportSkillInput(
        version='1.0.0',
        skill_md='---\nname: calculate-method\ndescription: Use for arithmetic.\n---\n' + INSTRUCTION,
    ))
    version = SkillVersion(
        skill_id=uuid4(), project_id=uuid4(), version='1.0.0',
        package=package, package_hash=skill_package_hash(package),
    )
    config = {
        'context_assembler': {'name': 'standard'},
        'context': {'allowed_sources': ['SYSTEM', 'USER_INPUT', 'SESSION', 'TOOL', 'SKILL'], 'skills': {}},
        'skills': {
            'bindings': [{'skill_id': str(version.skill_id), 'skill_version_id': str(version.id), 'enabled': True}],
            'snapshots': [version.snapshot()],
        },
    }
    agent = SimpleNamespace(
        id=uuid4(), project_id=version.project_id, provider='custom', model='controlled',
        temperature=0.2, max_output_tokens=1000, fallback_credential_id=None,
        session_mode='stateless', settings={'runtime_config': config},
    )
    transactions = _Transactions(version)
    runtime = _Runtime(agent, transactions)
    context = new_execution_context()
    context.project_id, context.agent_id = agent.project_id, agent.id
    if network:
        context.network_execution_id = uuid4()
        context.network_invocation_id = uuid4()
    request = AskInput(
        project_id=agent.project_id, agent_id=agent.id, message='Quanto é 1 + 1?',
        execution_context='playground',
        metadata={'source': 'network_runtime', 'defer_persistence': True} if network else {},
    )

    async def acceptance_io(self, input_dto):
        # Replace only standalone persistence; retain its real preparation wrapper.
        current_execution.get().run_id = uuid4()
        messages = self._build_messages(agent, None, [], input_dto.message, None)
        return (agent, None, uuid4(), 'fixture', None, {'enabled': False}, False,
                [], {}, False, [], messages, [])

    monkeypatch.setattr(ExplicitRuntimePersistenceMixin, '_prepare', acceptance_io)
    monkeypatch.setattr(preparation, 'prepare_tool_state', AsyncMock(return_value=([], {})))
    monkeypatch.setattr(preparation, 'prepare_rag_binding', AsyncMock(return_value=None))
    configure_skill_runtime(frozen_enabled_skills, SkillRuntime)
    configure_skill_binding_freezer(freeze_skill_bindings)
    token = current_execution.set(context)
    try:
        prepared = await runtime._prepare(request)
        model = _Model(version.id)
        execution = await run_instrumented_execution(
            llm_factory=SimpleNamespace(create_chat_model=lambda **kwargs: model),
            execute_single_tool=AsyncMock(), clean_json_answer=lambda value: value,
            agent=prepared[0], api_key='fixture', base_url=None, response_format={},
            json_enabled=False, has_tools=False, agent_tools=[], tool_name_to_id={},
            messages=prepared[11], context_assembler=build_runtime_context_assembler(),
        )
        assert [call.tool_name for call in execution.tool_calls] == ['skills_activate']
        assert execution.tool_calls[-1].output['output']['activated'] is True
        assert execution.result.content == 'SKILL_CONTEXT_REACHED_MODEL'
        assert len(model.received) == 2
        assert model.bound_names == {'skills_activate', 'skills_read_resource'}
        assert context.context_assembler_name == 'standard'
        assert context.prepare_started_at is not None
        snapshot = execution.llm_calls[-1]['context_snapshot']
        assert snapshot['manifest']['skills']['active_versions'] == [str(version.id)]
        assert any(item['source_type'] == 'SKILL' for item in snapshot['contributions'])
        if network:
            assert context.run_id == context.network_invocation_id
            assert transactions.read_count == 1
    finally:
        current_execution.reset(token)
