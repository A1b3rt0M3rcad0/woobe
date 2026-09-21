from __future__ import annotations

from uuid import uuid4

import pytest

from modules.agent.composition.runtime_contract_reader import AgentRuntimeContractReader
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.runtime_contract_compatibility import (
    compare_contract_schema,
    effective_external_context_contract_schema,
)


@pytest.mark.asyncio
async def test_agent_runtime_contract_reader_returns_output_and_external_context() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()

    try:
        async with session_factory() as session, session.begin():
            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="SDK contract Agent",
                    description="",
                    type="assistant",
                    behavior_spec=None,
                    system_prompt="",
                    provider="openai",
                    model="provider-mock",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.0,
                    max_output_tokens=128,
                    session_mode="stateful",
                    status="active",
                    settings={},
                )
            )
            await session.flush()
            session.add(
                AgentReleaseModel(
                    id=release_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    version="v1.0.0",
                    status="production",
                    snapshot_kind="release",
                    response_format={"type": "json", "strict": True},
                    output_schema={
                        "message": "string",
                        "confidence": "float",
                    },
                    external_context_contract={
                        "age": {
                            "schema": {"type": "integer"},
                            "required": True,
                            "model": {"expose": False},
                        },
                        "title": {
                            "schema": {"type": "string"},
                            "required": False,
                            "model": {"expose": True},
                        },
                    },
                    session_mode="stateful",
                )
            )

        snapshot = await AgentRuntimeContractReader(
            lambda: AgentUnitOfWork(engine).mark_read_only()
        ).read(
            agent_id=agent_id,
            project_id=project_id,
            environment="production",
        )

        output_result = compare_contract_schema(
            snapshot.output_contract,
            {
                "title": "SdkOutput",
                "type": "object",
                "properties": {
                    "message": {"title": "Message", "type": "string"},
                    "confidence": {"title": "Confidence", "type": "number"},
                },
                "required": ["message", "confidence"],
            },
        )
        external_result = compare_contract_schema(
            snapshot.external_context,
            {
                "type": "object",
                "properties": {
                    "age": {"type": "integer"},
                    "title": {"type": "string"},
                },
                "required": ["age"],
                "additionalProperties": False,
            },
        )

        assert snapshot.release_id == str(release_id)
        assert snapshot.release_version == "v1.0.0"
        assert output_result["valid"] is True
        assert external_result["valid"] is True
    finally:
        async with session_factory() as session, session.begin():
            release = await session.get(AgentReleaseModel, release_id)
            if release is not None:
                await session.delete(release)
            agent = await session.get(AgentModel, agent_id)
            if agent is not None:
                await session.delete(agent)
        await engine.dispose()


def test_network_effective_external_context_keeps_all_fields_optional_at_boundary() -> None:
    expected = effective_external_context_contract_schema(
        {
            "age": {
                "schema": {"type": "integer"},
                "consumers": {
                    "agent-a": {"required": True, "model": {"expose": False}},
                },
            },
            "title": {
                "schema": {"type": "string"},
                "consumers": {
                    "agent-b": {"required": True, "model": {"expose": True}},
                },
            },
        }
    )

    result = compare_contract_schema(
        expected,
        {
            "type": "object",
            "properties": {
                "age": {"type": "integer"},
            },
            "required": [],
            "additionalProperties": False,
        },
    )

    assert result["valid"] is False
    assert {
        issue["code"]
        for issue in result["issues"]
    } == {"FIELD_MISSING"}
    assert result["issues"][0]["field"] == "title"
