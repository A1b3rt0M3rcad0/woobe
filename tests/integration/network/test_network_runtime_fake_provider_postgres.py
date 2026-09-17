from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session as SyncSession

from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.models import AgentModel, ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.network.infra.services.service import NetworkApplicationService
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from modules.network.infra.runtime.loader import NetworkRuntimeLoader
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from woobe_workers.consumers.network.execution_worker import NetworkExecutionProcessor
from woobe_workers.composition.network_agent_runtime import ProjectRAIAgentInvoker
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.security.crypto import encrypt_secret


@pytest.mark.asyncio
async def test_network_runtime_executes_real_agent_against_fake_custom_provider_with_two_commits() -> None:
    settings = Settings()
    fake_provider_url = os.environ.get("WOOBE_TEST_FAKE_PROVIDER_URL")
    assert fake_provider_url, (
        "WOOBE_TEST_FAKE_PROVIDER_URL must point to the deterministic fake provider"
    )

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    credential_id = uuid4()
    provider_model_id = uuid4()
    agent_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    node_id = uuid4()

    definition = {
        "schema_version": 2,
        "root_node_id": str(node_id),
        "nodes": [
            {
                "id": str(node_id),
                "agent_id": str(agent_id),
                "label": "Fake Provider Agent",
                "capability_description": "Return a deterministic test response.",
                "position": {"x": 0.0, "y": 0.0},
                "binding": {"source": "draft", "release_id": None},
            }
        ],
        "edges": [],
        "settings": {
            "session_mode": "stateless",
            "max_depth": 2,
            "max_invocations": 4,
            "timeout_seconds": 30,
        },
    }
    external_context_contract = {
        "fields": {
            "customer_id": {
                "schema": {"type": "string"},
                "required": True,
                "scope": "run",
                "model": {"expose": False},
            }
        }
    }

    credential = ProviderCredentialModel(
        id=credential_id,
        project_id=project_id,
        provider="custom",
        name=f"fake-provider-{credential_id}",
        encrypted_secret=encrypt_secret("fake-api-key", settings.encryption_key),
        status="active",
        meta={
            "provider_family": "openai",
            "compatibility": "compatible",
            "base_url": fake_provider_url,
            "model_discovery_strategy": "openai_compatible_models",
        },
    )
    provider_model = ProviderModelModel(
        id=provider_model_id,
        project_id=project_id,
        provider_credential_id=credential_id,
        name="Fake Success",
        model="fake-success",
        status="active",
        meta={"source": "integration-test"},
    )
    agent = AgentModel(
        id=agent_id,
        project_id=project_id,
        provider_credential_id=credential_id,
        fallback_credential_id=None,
        name="network-fake-provider-agent",
        description="",
        type="assistant",
        system_prompt="Return the provider response without modification.",
        provider="custom",
        model="fake-success",
        fallback_provider=None,
        fallback_model=None,
        temperature=0.0,
        max_output_tokens=64,
        session_mode="stateless",
        status="active",
        settings={"external_context_contract": external_context_contract},
    )
    agent.provider_model_id = provider_model_id

    async with session_factory() as session, session.begin():
        # These fixtures intentionally use scalar FK ids instead of ORM relationships.
        # Flush each dependency before its consumer so the test setup is deterministic
        # on PostgreSQL. This setup commit is outside the lifecycle commit counter below.
        session.add(credential)
        await session.flush()

        session.add(provider_model)
        await session.flush()

        session.add(agent)
        await session.flush()

        session.add(
            NetworkModel(
                id=network_id,
                project_id=project_id,
                name=f"fake-provider-network-{network_id}",
                description="",
                draft_definition=definition,
                draft_revision=1,
                staging_version_id=None,
                production_version_id=None,
            )
        )
        await session.flush()

        session.add(
            NetworkSessionModel(
                id=network_session_id,
                network_id=network_id,
                network_version_id=None,
                project_id=project_id,
                origin="runtime_api",
                environment="draft",
                title="fake provider network session",
                tenant_id=None,
                user_id=None,
                external_session_id=None,
                status="active",
            )
        )

    service = NetworkApplicationService(
        session_factory,
        hard_max_depth=settings.network_max_depth_hard,
        hard_max_invocations=settings.network_max_invocations_hard,
        hard_timeout_seconds=settings.network_timeout_hard_seconds,
    )
    runtime_store = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
    http_executor = HttpToolExecutor(
        default_timeout_ms=settings.http_tool_timeout_max_ms,
        max_timeout_ms=settings.http_tool_timeout_max_ms,
        max_response_bytes=settings.http_tool_response_max_bytes,
        allow_local_networks=True,
    )
    processor = NetworkExecutionProcessor(
        loader=NetworkRuntimeLoader(session_factory),
        store=runtime_store,
        finalizer=NetworkRuntimeFinalizer(session_factory),
        agent_invoker=ProjectRAIAgentInvoker(settings, http_executor),
        lease_ttl_seconds=settings.network_execution_lease_ttl_seconds,
        heartbeat_seconds=settings.network_execution_lease_heartbeat_seconds,
        worker_id=f"network-integration-{uuid4()}",
    )

    commits = 0

    def after_commit(_session) -> None:
        nonlocal commits
        commits += 1

    event.listen(SyncSession, "after_commit", after_commit)
    try:
        submitted = await service.submit_execution(
            network_id=network_id,
            project_id=project_id,
            network_session_id=network_session_id,
            message="hello network",
            external_context={"customer_id": "cus-network-1"},
            idempotency_key=f"fake-provider-{uuid4()}",
            expected_draft_revision=1,
        )
        await processor.process(submitted.id)
    finally:
        event.remove(SyncSession, "after_commit", after_commit)
        await http_executor.aclose()

    assert commits == 2, (
        "Network lifecycle must remain one Acceptance commit plus one Finalization commit"
    )

    async with session_factory() as session:
        execution = await session.get(NetworkExecutionModel, submitted.id)
        invocations = list(
            (
                await session.scalars(
                    select(NetworkInvocationModel).where(
                        NetworkInvocationModel.network_execution_id == submitted.id
                    )
                )
            ).all()
        )
        runs = list(
            (
                await session.scalars(
                    select(AgentRunModel).where(
                        AgentRunModel.network_execution_id == submitted.id
                    )
                )
            ).all()
        )

    assert execution is not None
    assert execution.external_context_snapshot == {"customer_id": "cus-network-1"}
    assert execution.status == "completed", (
        execution.failure_code,
        execution.failure_detail,
    )
    assert execution.output_message == "Woobe release gate passed"
    assert execution.failure_code is None

    assert len(invocations) == 1
    invocation = invocations[0]
    assert invocation.node_id == node_id
    assert invocation.agent_id == agent_id
    assert invocation.status == "completed"
    assert invocation.output_message == "Woobe release gate passed"

    assert len(runs) == 1
    run = runs[0]
    assert run.id == invocation.id
    assert run.network_invocation_id == invocation.id
    assert run.origin == "network_runtime"
    assert run.status == "completed"
    assert run.failure_code is None
    assert run.result["answer"] == "Woobe release gate passed"
    assert run.result["provider"] == "custom"
    assert run.result["model"] == "fake-success"
    assert run.usage["input_tokens"] == 7
    assert run.usage["output_tokens"] == 5
    assert run.usage["total_tokens"] == 12

    await engine.dispose()
