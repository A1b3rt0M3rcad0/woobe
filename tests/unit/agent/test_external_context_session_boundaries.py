from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.infra.database.runtime_session_repository import (
    SQLAlchemyRuntimeSessionRepository,
)
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from shared.contracts.errors import ConflictError
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.presentation.contracts import OperationOutcome, OperationRequest


def _session_conflict() -> ConflictError:
    error = ConflictError(
        "Session-scoped External Context is already fixed and cannot be supplied again: client_id"
    )
    error.code = "EXTERNAL_CONTEXT_SESSION_FIELD_ALREADY_SET"
    error.fields = ["client_id"]
    error.scope = "session"
    error.reason = "already_set"
    return error


@pytest.mark.asyncio
async def test_runtime_session_repository_persists_external_context_snapshot() -> None:
    session_id = uuid4()
    snapshot = {"client_id": "client-123"}
    model = SimpleNamespace()
    entity = SimpleNamespace(
        id=session_id,
        runtime_environment="production",
        opened_release_id=None,
        external_session_id=None,
        tenant_id=None,
        user_id=None,
        status="active",
        mode="chat",
        data=None,
        external_context_snapshot=snapshot,
        last_message_at=None,
    )

    repo = SQLAlchemyRuntimeSessionRepository.__new__(
        SQLAlchemyRuntimeSessionRepository
    )
    repo._base = SimpleNamespace(
        _get_model_by_id=AsyncMock(return_value=model),
        _flush=AsyncMock(),
    )
    repo._to_entity = lambda value: entity

    await repo.update(entity)

    assert model.external_context_snapshot == snapshot
    repo._base._flush.assert_awaited_once()


class _ConflictUseCase:
    async def execute(self, _input):
        raise _session_conflict()


@pytest.mark.asyncio
async def test_agent_controller_preserves_structured_session_conflict() -> None:
    controller = AskAgentController(_ConflictUseCase())
    response = await controller.handle(
        OperationRequest(
            body={
                "project_id": uuid4(),
                "agent_id": uuid4(),
                "message": "hello",
            }
        )
    )

    assert response.outcome is OperationOutcome.CONFLICT
    assert response.body["data"] == {
        "code": "EXTERNAL_CONTEXT_SESSION_FIELD_ALREADY_SET",
        "fields": ["client_id"],
        "scope": "session",
        "reason": "already_set",
    }


@pytest.mark.asyncio
async def test_agent_stream_preserves_structured_session_conflict_frame() -> None:
    service = AskAgentStreamService(
        _ConflictUseCase(),
        SimpleNamespace(),
        state_store=InMemoryExecutionStateStore(),
    )
    channel = RuntimeStreamChannel()
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="hello",
    )

    with pytest.raises(ConflictError):
        await service._run_execution(input_dto, channel)

    event = channel.queue.get_nowait()
    assert event.event_type == "error"
    assert event.payload["status_code"] == 409
    assert event.payload["code"] == "EXTERNAL_CONTEXT_SESSION_FIELD_ALREADY_SET"
    assert event.payload["fields"] == ["client_id"]
    assert event.payload["scope"] == "session"
    assert event.payload["reason"] == "already_set"
