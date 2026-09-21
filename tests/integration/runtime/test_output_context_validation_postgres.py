from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.network.infra.database.models import NetworkModel
from modules.network.infra.database.schema_extensions import NetworkVersionModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.security.principal import ProjectApiPrincipal
from woobe_api.http.shared.output_context_validation import (
    OutputContextValidationRequest,
    validate_output_context,
)


def _request(engine) -> Request:
    app = FastAPI()
    app.state.async_engine = engine
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/output-context/validate",
            "headers": [],
            "app": app,
        }
    )


def _principal(*, project_id, target_type: str, target_id):
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=project_id,
        key_prefix="rai_live_contract_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        agent_id=target_id if target_type == "agent" else None,
        target_type=target_type,
        target_id=target_id,
        environment="production",
        interfaces=frozenset({"stream"}),
        authenticated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_agent_output_context_validation_uses_published_release_schema() -> None:
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
                    session_mode="stateful",
                )
            )

        result = await validate_output_context(
            _request(engine),
            _principal(
                project_id=project_id,
                target_type="agent",
                target_id=agent_id,
            ),
            OutputContextValidationRequest(
                output_context={
                    "title": "SdkOutput",
                    "type": "object",
                    "properties": {
                        "message": {"title": "Message", "type": "string"},
                        "confidence": {"title": "Confidence", "type": "number"},
                    },
                    "required": ["message", "confidence"],
                }
            ),
        )

        assert result["data"]["valid"] is True
        assert result["data"]["release_id"] == str(release_id)
        assert result["data"]["release_version"] == "v1.0.0"
        assert result["data"]["issues"] == []
        assert (
            result["data"]["expected_hash"]
            == result["data"]["received_hash"]
        )
    finally:
        async with session_factory() as session, session.begin():
            release = await session.get(AgentReleaseModel, release_id)
            if release is not None:
                await session.delete(release)
            agent = await session.get(AgentModel, agent_id)
            if agent is not None:
                await session.delete(agent)
        await engine.dispose()


@pytest.mark.asyncio
async def test_network_output_context_validation_detects_sdk_schema_mismatch() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id = uuid4()
    network_id = uuid4()
    version_id = uuid4()

    try:
        async with session_factory() as session, session.begin():
            network = NetworkModel(
                id=network_id,
                project_id=project_id,
                name=f"SDK contract Network {network_id}",
                description="",
                draft_definition={},
                draft_revision=0,
                staging_version_id=None,
                production_version_id=None,
            )
            session.add(network)
            await session.flush()

            version = NetworkVersionModel(
                id=version_id,
                network_id=network_id,
                project_id=project_id,
                kind="release",
                version="v2.0.0",
                definition={},
                resolved_bindings={},
                composition_hash="a" * 64,
                created_by=None,
            )
            version.public_output_contract = {
                "enabled": True,
                "type": "json",
                "strict": True,
                "schema": {
                    "message": "string",
                },
            }
            session.add(version)
            await session.flush()
            network.production_version_id = version_id

        result = await validate_output_context(
            _request(engine),
            _principal(
                project_id=project_id,
                target_type="network",
                target_id=network_id,
            ),
            OutputContextValidationRequest(
                output_context={
                    "type": "object",
                    "properties": {
                        "message": {"type": "integer"},
                    },
                    "required": ["message"],
                }
            ),
        )

        assert result["data"]["valid"] is False
        assert result["data"]["release_id"] == str(version_id)
        assert result["data"]["release_version"] == "v2.0.0"
        assert result["data"]["issues"] == [
            {
                "code": "OUTPUT_CONTEXT_MISMATCH",
                "message": (
                    "SDK output_context does not match the published "
                    "Woobe Output Contract"
                ),
            }
        ]
        assert (
            result["data"]["expected_hash"]
            != result["data"]["received_hash"]
        )
    finally:
        async with session_factory() as session, session.begin():
            network = await session.get(NetworkModel, network_id)
            if network is not None:
                network.production_version_id = None
            version = await session.get(NetworkVersionModel, version_id)
            if version is not None:
                await session.delete(version)
            if network is not None:
                await session.delete(network)
        await engine.dispose()
