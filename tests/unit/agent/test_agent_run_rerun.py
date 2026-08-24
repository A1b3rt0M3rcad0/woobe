from __future__ import annotations

from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskOutput
from modules.agent.application.use_cases.rerun_agent_run import RerunAgentRunUseCase
from modules.agent.domain.run import AgentRun, AgentRunStatus


class _Reader:
    def __init__(self, run):
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run and self.run.id == run_id else None


class _Executor:
    def __init__(self):
        self.input = None

    async def execute(self, input_dto):
        self.input = input_dto
        return AskOutput(run_id=uuid4(), answer="rerun answer")


def _run(*, environment="production", release_id=None, snapshot=None):
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        agent_release_id=release_id,
        trace_id=uuid4(),
        environment=environment,
        origin="runtime_api",
        input_message="original input",
        execution_snapshot=snapshot or {},
        status=AgentRunStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_production_rerun_creates_new_execution_against_original_release() -> None:
    release_id = uuid4()
    source = _run(environment="production", release_id=release_id)
    executor = _Executor()
    use_case = RerunAgentRunUseCase(_Reader(source), executor)

    result = await use_case.execute(run_id=source.id, project_id=source.project_id)

    assert result.run_id is not None
    assert result.run_id != source.id
    assert executor.input.loaded_release_id == release_id
    assert executor.input.execution_context == "production"
    assert executor.input.message == "original input"
    assert executor.input.session_id == source.session_id
    assert executor.input.metadata["rerun_of_run_id"] == str(source.id)


@pytest.mark.asyncio
async def test_draft_rerun_reuses_frozen_agent_tool_rag_and_output_snapshots() -> None:
    tool_id = uuid4()
    provider_model_id = uuid4()
    provider_credential_id = uuid4()
    fallback_provider_model_id = uuid4()
    fallback_credential_id = uuid4()
    knowledge_version_id = uuid4()
    source = _run(
        environment="draft",
        snapshot={
            "agent": {
                "system_prompt": "frozen prompt",
                "provider_model_id": str(provider_model_id),
                "provider_credential_id": str(provider_credential_id),
                "provider": "openai",
                "model": "gpt-test",
                "fallback_provider_model_id": str(fallback_provider_model_id),
                "fallback_credential_id": str(fallback_credential_id),
                "fallback_provider": "openai",
                "fallback_model": "gpt-fallback",
                "temperature": 0.1,
                "max_output_tokens": 500,
                "session_mode": "stateful",
                "settings": {
                    "knowledge_version_id": str(knowledge_version_id),
                    "response_format": {
                        "enabled": True,
                        "type": "json",
                        "schema": {"type": "object", "required": ["answer"]},
                    },
                    "runtime_config": {
                        "rag": {
                            "top_k": 4,
                            "candidate_k": 8,
                            "grounding_policy": "required",
                        },
                        "tools": {"permissions": {}},
                    },
                },
            },
            "knowledge": {
                "knowledge_version_id": str(knowledge_version_id),
                "vector_snapshot_id": str(uuid4()),
                "vector_snapshot_hash": "frozen-vector-hash",
            },
            "tools": [
                {
                    "id": str(tool_id),
                    "name": "frozen_tool",
                    "snapshot_hash": "hash",
                }
            ],
        },
    )
    executor = _Executor()
    use_case = RerunAgentRunUseCase(_Reader(source), executor)

    await use_case.execute(run_id=source.id, project_id=source.project_id)

    assert executor.input.execution_context == "playground"
    assert executor.input.loaded_release_id is None
    assert executor.input.session_id == source.session_id
    override = executor.input.snapshot_override
    assert override["system_prompt"] == "frozen prompt"
    assert override["provider_model_id"] == str(provider_model_id)
    assert override["provider_credential_id"] == str(provider_credential_id)
    assert override["fallback_provider_model_id"] == str(fallback_provider_model_id)
    assert override["fallback_credential_id"] == str(fallback_credential_id)
    assert override["fallback_provider"] == "openai"
    assert override["fallback_model"] == "gpt-fallback"
    assert override["knowledge_version_id"] == str(knowledge_version_id)
    assert override["response_format"]["schema"]["required"] == ["answer"]
    assert override["runtime_config"]["rag"] == {
        "top_k": 4,
        "candidate_k": 8,
        "grounding_policy": "required",
    }
    assert override["runtime_config"]["tools"]["tool_ids"] == [str(tool_id)]
    assert override["runtime_config"]["tools"]["snapshots"][0]["name"] == "frozen_tool"


@pytest.mark.asyncio
async def test_running_run_cannot_be_rerun() -> None:
    source = _run()
    source.status = AgentRunStatus.RUNNING
    use_case = RerunAgentRunUseCase(_Reader(source), _Executor())

    with pytest.raises(Exception, match="running Agent Run"):
        await use_case.execute(run_id=source.id, project_id=source.project_id)
