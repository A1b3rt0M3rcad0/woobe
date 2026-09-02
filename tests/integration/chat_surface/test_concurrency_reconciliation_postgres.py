from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from modules.chat_surface.application.dtos.message_request import BeginMessageRequestInput
from modules.chat_surface.application.use_cases.message_lifecycle import (
    BeginChatSurfaceMessageUseCase,
)
from modules.chat_surface.infra.database.message_request_repository import (
    SQLAlchemyChatSurfaceMessageRequestRepository,
)
from modules.chat_surface.infra.database.models import (
    ChatSurfaceMessageRequestModel,
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.core.infra.database.models import ProjectModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_stale_request_from_previous_session_does_not_consume_surface_concurrency_forever() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    surface_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    stale_binding_id = uuid4()
    current_binding_id = uuid4()
    stale_session_id = uuid4()
    current_session_id = uuid4()
    stale_request_id = uuid4()
    now = datetime.now(UTC)
    stale_at = now - timedelta(minutes=11)

    try:
        async with session_factory() as session, session.begin():
            session.add(
                ProjectModel(
                    id=project_id,
                    workspace_id=uuid4(),
                    name="ChatSurface concurrency reconciliation",
                    slug=f"chat-concurrency-{project_id}",
                    status="active",
                    data={},
                )
            )
            await session.flush()

            session.add(
                ChatSurfaceModel(
                    id=surface_id,
                    public_id=f"cs_{surface_id.hex[:20]}",
                    project_id=project_id,
                    name="Concurrency Surface",
                    normalized_name="concurrency surface",
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
                    max_concurrent_runs=1,
                    session_token_ttl_seconds=900,
                    token_epoch=1,
                    created_by=None,
                    activated_at=now,
                    archived_at=None,
                )
            )
            await session.flush()

            session.add_all(
                [
                    ChatSurfaceSessionBindingModel(
                        id=stale_binding_id,
                        chat_surface_id=surface_id,
                        project_id=project_id,
                        target_type="agent",
                        target_id=agent_id,
                        target_release_id=release_id,
                        session_id=stale_session_id,
                        surface_credential_id=uuid4(),
                        idempotency_key=f"session-{stale_binding_id}",
                        external_reference=None,
                        metadata_=None,
                        status="active",
                    ),
                    ChatSurfaceSessionBindingModel(
                        id=current_binding_id,
                        chat_surface_id=surface_id,
                        project_id=project_id,
                        target_type="agent",
                        target_id=agent_id,
                        target_release_id=release_id,
                        session_id=current_session_id,
                        surface_credential_id=uuid4(),
                        idempotency_key=f"session-{current_binding_id}",
                        external_reference=None,
                        metadata_=None,
                        status="active",
                    ),
                ]
            )
            await session.flush()

            stale_request = ChatSurfaceMessageRequestModel(
                id=stale_request_id,
                session_binding_id=stale_binding_id,
                idempotency_key=f"message-{stale_request_id}",
                status="streaming",
                target_run_id=None,
                error_code=None,
                completed_at=None,
            )
            session.add(stale_request)
            await session.flush()
            stale_request.created_at = stale_at
            stale_request.updated_at = stale_at

        uow = ChatSurfaceUnitOfWork(engine)
        async with uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            use_case = BeginChatSurfaceMessageUseCase(
                repository,
                max_metadata_bytes=settings.runtime_max_metadata_bytes,
            )
            result = await use_case.execute(
                BeginMessageRequestInput(
                    surface_id=surface_id,
                    session_binding_id=current_binding_id,
                    idempotency_key="new-session-message",
                )
            )

        async with session_factory() as session:
            stale_after = await session.get(
                ChatSurfaceMessageRequestModel,
                stale_request_id,
            )
            created_after = await session.get(
                ChatSurfaceMessageRequestModel,
                result.request.id,
            )

        assert result.created is True
        assert stale_after is not None
        assert stale_after.status == "failed"
        assert stale_after.error_code == "runtime_lease_expired"
        assert stale_after.completed_at is not None
        assert created_after is not None
        assert created_after.session_binding_id == current_binding_id
        assert created_after.status == "accepted"
    finally:
        await engine.dispose()
