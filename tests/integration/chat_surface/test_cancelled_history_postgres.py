from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import uuid6

from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    MessageModel,
    SessionModel,
)
from modules.agent.infra.database.run_models import AgentRunModel
from modules.chat_surface.infra.database.models import (
    ChatSurfaceMessageRequestModel,
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.service import ChatSurfaceService
from modules.core.infra.database.models import ProjectModel
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


async def _flush(session) -> None:
    """Persist one FK dependency layer before constructing the next one."""
    await session.flush()


@pytest.mark.asyncio
async def test_cancelled_agent_chat_surface_history_keeps_request_run_and_partial_message_coherent() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    surface_id = uuid4()
    binding_id = uuid4()
    session_id = uuid4()
    run_id = uuid4()
    request_id = uuid4()
    user_message_id = uuid6.uuid7()
    assistant_message_id = uuid6.uuid7()
    now = datetime.now(UTC)

    try:
        async with session_factory() as session, session.begin():
            session.add(
                ProjectModel(
                    id=project_id,
                    workspace_id=uuid4(),
                    name="ChatSurface Agent cancellation",
                    slug=f"chat-agent-{project_id}",
                    status="active",
                    data={},
                )
            )
            await _flush(session)

            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="ChatSurface Agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="test",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateful",
                    status="active",
                    settings={},
                )
            )
            await _flush(session)

            session.add(
                AgentReleaseModel(
                    id=release_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    version="1.0.0",
                    status="production",
                    snapshot_kind="release",
                    prompt_version_id=None,
                    contract_version_id=None,
                    knowledge_version_id=None,
                    model_config_version_id=None,
                    name="Production",
                    description="",
                    system_prompt="",
                    response_format=None,
                    output_schema=None,
                    provider="openai",
                    model="test",
                    provider_credential_id=None,
                    fallback_provider=None,
                    fallback_model=None,
                    fallback_credential_id=None,
                    base_url=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateful",
                    agent_status="active",
                    collection_ids=[],
                    runtime_config={},
                    release_notes="chat cancellation test",
                    risk_score=None,
                    created_by=None,
                    promoted_by=None,
                    promoted_at=now,
                )
            )
            await _flush(session)

            session.add(
                ChatSurfaceModel(
                    id=surface_id,
                    public_id=f"cs_{surface_id.hex[:20]}",
                    project_id=project_id,
                    name="Agent Surface",
                    normalized_name="agent surface",
                    description=None,
                    target_type="agent",
                    target_id=agent_id,
                    target_release_id=release_id,
                    environment="production",
                    status="active",
                    access_mode="backend_managed",
                    allowed_origins=["https://app.example.com"],
                    appearance_config={},
                    requests_per_minute=30,
                    max_concurrent_runs=10,
                    session_token_ttl_seconds=900,
                    token_epoch=1,
                    created_by=None,
                    activated_at=now,
                    archived_at=None,
                )
            )
            await _flush(session)

            session.add(
                SessionModel(
                    id=session_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    runtime_environment="production",
                    opened_release_id=release_id,
                    chat_surface_id=surface_id,
                    origin="chat_surface",
                    external_session_id=None,
                    tenant_id=str(surface_id),
                    user_id=None,
                    status="active",
                    mode="chat",
                    data={"source": "chat_surface"},
                    last_message_at=now,
                )
            )
            await _flush(session)

            session.add(
                ChatSurfaceSessionBindingModel(
                    id=binding_id,
                    chat_surface_id=surface_id,
                    project_id=project_id,
                    target_type="agent",
                    target_id=agent_id,
                    target_release_id=release_id,
                    session_id=session_id,
                    surface_credential_id=uuid4(),
                    idempotency_key=f"session-{binding_id}",
                    external_reference=None,
                    metadata_=None,
                    status="active",
                )
            )
            await _flush(session)

            session.add_all(
                [
                    MessageModel(
                        id=user_message_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        role="user",
                        content="write a long answer",
                        input_tokens=None,
                        output_tokens=None,
                        cost_usd=None,
                        data={"source": "chat_surface"},
                    ),
                    MessageModel(
                        id=assistant_message_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        role="assistant",
                        content="partial answer",
                        input_tokens=None,
                        output_tokens=None,
                        cost_usd=None,
                        data={"partial": True, "cancelled": True},
                    ),
                ]
            )
            await _flush(session)

            session.add(
                AgentRunModel(
                    id=run_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    agent_release_id=release_id,
                    input_message_id=user_message_id,
                    output_message_id=assistant_message_id,
                    trace_id=uuid4(),
                    environment="production",
                    origin="chat_surface",
                    status="cancelled",
                    input_message="write a long answer",
                    execution_snapshot={},
                    usage=None,
                    result={
                        "answer": "partial answer",
                        "partial": True,
                        "cancelled": True,
                    },
                    failure_code=None,
                    failure_detail=None,
                    network_execution_id=None,
                    network_invocation_id=None,
                    parent_run_id=None,
                    rerun_of_run_id=None,
                    started_at=now,
                    completed_at=now,
                )
            )
            await _flush(session)

            session.add(
                ChatSurfaceMessageRequestModel(
                    id=request_id,
                    session_binding_id=binding_id,
                    idempotency_key=f"message-{request_id}",
                    status="streaming",
                    target_run_id=run_id,
                    error_code=None,
                    completed_at=None,
                )
            )

        service = ChatSurfaceService(session_factory, SimpleNamespace())
        await service.mark_message(
            request_id,
            status="cancelled",
            target_run_id=run_id,
        )
        history = await service.list_messages(
            SimpleNamespace(
                binding=SimpleNamespace(
                    target_type="agent",
                    session_id=session_id,
                )
            ),
            limit=50,
            cursor=None,
        )

        async with session_factory() as session:
            request = await session.get(ChatSurfaceMessageRequestModel, request_id)
            run = await session.get(AgentRunModel, run_id)

        assert request is not None
        assert request.status == "cancelled"
        assert request.target_run_id == run_id
        assert request.completed_at is not None
        assert request.error_code is None

        assert run is not None
        assert run.status == "cancelled"
        assert run.input_message_id == user_message_id
        assert run.output_message_id == assistant_message_id
        assert run.result == {
            "answer": "partial answer",
            "partial": True,
            "cancelled": True,
        }
        assert history["has_next"] is False
        assert [(item["role"], item["content"]) for item in history["items"]] == [
            ("user", "write a long answer"),
            ("assistant", "partial answer"),
        ]
        assert history["items"][1]["data"]["partial"] is True
        assert history["items"][1]["data"]["cancelled"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_network_chat_surface_history_keeps_request_execution_and_partial_message_coherent() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    network_id = uuid4()
    version_id = uuid4()
    surface_id = uuid4()
    binding_id = uuid4()
    session_id = uuid4()
    execution_id = uuid4()
    request_id = uuid4()
    user_message_id = uuid6.uuid7()
    assistant_message_id = uuid6.uuid7()
    now = datetime.now(UTC)

    try:
        async with session_factory() as session, session.begin():
            session.add(
                ProjectModel(
                    id=project_id,
                    workspace_id=uuid4(),
                    name="ChatSurface Network cancellation",
                    slug=f"chat-network-{project_id}",
                    status="active",
                    data={},
                )
            )
            await _flush(session)

            session.add(
                NetworkModel(
                    id=network_id,
                    project_id=project_id,
                    name=f"ChatSurface Network {network_id}",
                    description="",
                    draft_definition={},
                    draft_revision=1,
                    staging_version_id=None,
                    production_version_id=version_id,
                )
            )
            await _flush(session)

            session.add(
                NetworkVersionModel(
                    id=version_id,
                    network_id=network_id,
                    project_id=project_id,
                    kind="release",
                    version="1.0.0",
                    definition={"schema_version": 2, "nodes": [], "edges": []},
                    resolved_bindings={},
                    composition_hash="0" * 64,
                    created_by=None,
                    rollback_of_version_id=None,
                    source_version_id=None,
                    activation_kind="publish",
                    change_description="chat cancellation test",
                )
            )
            await _flush(session)

            session.add(
                ChatSurfaceModel(
                    id=surface_id,
                    public_id=f"cs_{surface_id.hex[:20]}",
                    project_id=project_id,
                    name="Network Surface",
                    normalized_name="network surface",
                    description=None,
                    target_type="network",
                    target_id=network_id,
                    target_release_id=version_id,
                    environment="production",
                    status="active",
                    access_mode="backend_managed",
                    allowed_origins=["https://app.example.com"],
                    appearance_config={},
                    requests_per_minute=30,
                    max_concurrent_runs=10,
                    session_token_ttl_seconds=900,
                    token_epoch=1,
                    created_by=None,
                    activated_at=now,
                    archived_at=None,
                )
            )
            await _flush(session)

            session.add(
                NetworkSessionModel(
                    id=session_id,
                    network_id=network_id,
                    network_version_id=version_id,
                    project_id=project_id,
                    chat_surface_id=surface_id,
                    origin="chat_surface",
                    environment="production",
                    title="ChatSurface session",
                    tenant_id=str(surface_id),
                    user_id=None,
                    external_session_id=None,
                    status="active",
                    last_message_at=now,
                )
            )
            await _flush(session)

            session.add(
                ChatSurfaceSessionBindingModel(
                    id=binding_id,
                    chat_surface_id=surface_id,
                    project_id=project_id,
                    target_type="network",
                    target_id=network_id,
                    target_release_id=version_id,
                    session_id=session_id,
                    surface_credential_id=uuid4(),
                    idempotency_key=f"session-{binding_id}",
                    external_reference=None,
                    metadata_=None,
                    status="active",
                )
            )
            await _flush(session)

            session.add(
                NetworkExecutionModel(
                    id=execution_id,
                    network_id=network_id,
                    network_version_id=version_id,
                    network_session_id=session_id,
                    project_id=project_id,
                    input_message="ask connected agents",
                    draft_revision=None,
                    definition_snapshot=None,
                    resolved_bindings_snapshot=None,
                    output_message="partial network answer",
                    status="cancelled",
                    idempotency_key=f"execution-{execution_id}",
                    root_trace_id=uuid4(),
                    attempt=1,
                    lease_owner=None,
                    lease_generation=0,
                    lease_expires_at=None,
                    heartbeat_at=None,
                    cancel_requested_at=now,
                    failure_code=None,
                    failure_detail=None,
                    last_event_sequence=3,
                    started_at=now,
                    completed_at=now,
                )
            )
            await _flush(session)

            session.add_all(
                [
                    NetworkMessageModel(
                        id=user_message_id,
                        network_session_id=session_id,
                        network_execution_id=execution_id,
                        project_id=project_id,
                        role="user",
                        content="ask connected agents",
                        data={"source": "chat_surface"},
                    ),
                    NetworkMessageModel(
                        id=assistant_message_id,
                        network_session_id=session_id,
                        network_execution_id=execution_id,
                        project_id=project_id,
                        role="assistant",
                        content="partial network answer",
                        data={"partial": True, "cancelled": True},
                    ),
                ]
            )
            await _flush(session)

            session.add(
                ChatSurfaceMessageRequestModel(
                    id=request_id,
                    session_binding_id=binding_id,
                    idempotency_key=f"message-{request_id}",
                    status="streaming",
                    target_run_id=execution_id,
                    error_code=None,
                    completed_at=None,
                )
            )

        service = ChatSurfaceService(session_factory, SimpleNamespace())
        await service.mark_message(
            request_id,
            status="cancelled",
            target_run_id=execution_id,
        )
        history = await service.list_messages(
            SimpleNamespace(
                binding=SimpleNamespace(
                    target_type="network",
                    session_id=session_id,
                )
            ),
            limit=50,
            cursor=None,
        )

        async with session_factory() as session:
            request = await session.get(ChatSurfaceMessageRequestModel, request_id)
            execution = await session.get(NetworkExecutionModel, execution_id)

        assert request is not None
        assert request.status == "cancelled"
        assert request.target_run_id == execution_id
        assert request.completed_at is not None
        assert request.error_code is None

        assert execution is not None
        assert execution.status == "cancelled"
        assert execution.output_message == "partial network answer"
        assert history["has_next"] is False
        assert [(item["role"], item["content"]) for item in history["items"]] == [
            ("user", "ask connected agents"),
            ("assistant", "partial network answer"),
        ]
        assert history["items"][1]["data"]["partial"] is True
        assert history["items"][1]["data"]["cancelled"] is True
    finally:
        await engine.dispose()
