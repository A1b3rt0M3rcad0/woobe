from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.use_cases.public_runtime_request_preparer import (
    PublicRuntimeRequestPreparer,
)
from modules.agent.domain.entities import AgentRelease, Session
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import (
    RuntimeEnvironmentNotReadyError,
    SessionNotFoundError,
)
from modules.agent.presentation.controllers.public_runtime_controllers import (
    PublicRunController,
)
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.security.principal import ProjectApiPrincipal


def runtime_principal(environment: str = "production") -> ProjectApiPrincipal:
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=uuid4(),
        key_prefix="rai_live_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        agent_id=uuid4(),
        environment=environment,
        interfaces=frozenset({"http", "stream", "jobs"}),
        authenticated_at=datetime.now(UTC),
    )


def test_public_request_forbids_internal_routing_fields() -> None:
    with pytest.raises(PydanticValidationError):
        PublicRunRequest(
            message="Hello",
            agent_id=uuid4(),
            project_id=uuid4(),
            execution_context="production",
        )


@pytest.mark.asyncio
async def test_public_run_maps_runtime_key_binding_to_internal_request() -> None:
    principal = runtime_principal("staging")
    internal_handler = AsyncMock(
        return_value=OperationResult(outcome="success", body={"success": True, "data": {}})
    )
    request_preparer = AsyncMock(side_effect=lambda payload, *_: payload)
    controller = PublicRunController(internal_handler, request_preparer)
    request = OperationRequest(
        principal=principal,
        body={"message": "Hello", "session_id": None},
    )

    response = await controller.handle(request)

    assert response.outcome == "success"
    prepared_args = request_preparer.await_args.args
    assert prepared_args[1:] == (
        principal.project_id,
        principal.agent_id,
        "staging",
    )
    mapped_request = internal_handler.await_args.args[0]
    assert mapped_request.body == {
        "message": "Hello",
        "session_id": None,
        "tenant_id": None,
        "user_id": None,
        "metadata": {"source": "public_runtime"},
        "external_context": None,
        "project_id": principal.project_id,
        "agent_id": principal.agent_id,
        "execution_context": "staging",
    }


@pytest.mark.asyncio
async def test_request_preparer_rejects_missing_production_release() -> None:
    release_repo = SimpleNamespace(
        get_active_production=AsyncMock(return_value=None),
        list_by_status=AsyncMock(),
    )
    session_repo = SimpleNamespace(get_by_id=AsyncMock())
    agent_repo = SimpleNamespace(get_by_id=AsyncMock())
    preparer = PublicRuntimeRequestPreparer(release_repo, session_repo, agent_repo)
    agent_id = uuid4()

    with pytest.raises(RuntimeEnvironmentNotReadyError, match="No production release"):
        await preparer.prepare(
            PublicRunRequest(message="Hello"),
            project_id=uuid4(),
            agent_id=agent_id,
            environment="production",
        )


@pytest.mark.asyncio
async def test_request_preparer_ignores_session_for_stateless_release() -> None:
    project_id = uuid4()
    release = AgentRelease(
        agent_id=uuid4(),
        status=ReleaseStatus.staging,
        session_mode="stateless",
    )
    release_repo = SimpleNamespace(
        get_active_production=AsyncMock(),
        list_by_status=AsyncMock(return_value=[release]),
    )
    session_repo = SimpleNamespace(get_by_id=AsyncMock())
    agent_repo = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(
                project_id=project_id,
                session_mode="stateless",
            )
        )
    )
    preparer = PublicRuntimeRequestPreparer(release_repo, session_repo, agent_repo)

    prepared = await preparer.prepare(
        PublicRunRequest(message="Hello", session_id=uuid4()),
        project_id=project_id,
        agent_id=release.agent_id,
        environment="staging",
    )

    assert prepared.session_id is None
    session_repo.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_preparer_rejects_session_from_another_agent() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        status=ReleaseStatus.production,
        session_mode="stateful",
    )
    release_repo = SimpleNamespace(
        get_active_production=AsyncMock(return_value=release),
        list_by_status=AsyncMock(),
    )
    session_repo = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=Session(
                id=session_id,
                project_id=project_id,
                agent_id=uuid4(),
            )
        )
    )
    agent_repo = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(
                project_id=project_id,
                session_mode="stateful",
            )
        )
    )
    preparer = PublicRuntimeRequestPreparer(release_repo, session_repo, agent_repo)

    with pytest.raises(SessionNotFoundError):
        await preparer.prepare(
            PublicRunRequest(message="Hello", session_id=session_id),
            project_id=project_id,
            agent_id=agent_id,
            environment="production",
        )
