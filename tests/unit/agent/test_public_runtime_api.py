from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.use_cases.public_runtime_environment_validator import (
    PublicRuntimeEnvironmentValidator,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import RuntimeEnvironmentNotReadyError
from modules.agent.presentation.controllers.public_runtime_controllers import (
    PublicRunController,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
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
        authenticated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
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
        return_value=Response(status_code=200, body={"success": True, "data": {}})
    )
    preflight = AsyncMock()
    controller = PublicRunController(internal_handler, preflight)
    request = Request(
        principal=principal,
        body={"message": "Hello", "session_id": None},
    )

    response = await controller.handle(request)

    assert response.status_code == 200
    preflight.assert_awaited_once_with(principal.agent_id, "staging")
    mapped_request = internal_handler.await_args.args[0]
    assert mapped_request.body == {
        "message": "Hello",
        "session_id": None,
        "tenant_id": None,
        "user_id": None,
        "metadata": None,
        "project_id": principal.project_id,
        "agent_id": principal.agent_id,
        "execution_context": "staging",
    }


@pytest.mark.asyncio
async def test_environment_validator_rejects_missing_production_release() -> None:
    repo = SimpleNamespace(
        get_active_production=AsyncMock(return_value=None),
        list_by_status=AsyncMock(),
    )
    validator = PublicRuntimeEnvironmentValidator(repo)
    agent_id = uuid4()

    with pytest.raises(RuntimeEnvironmentNotReadyError, match="No production release"):
        await validator.validate(agent_id, "production")


@pytest.mark.asyncio
async def test_environment_validator_accepts_current_staging_release() -> None:
    release = AgentRelease(agent_id=uuid4(), status=ReleaseStatus.staging)
    repo = SimpleNamespace(
        get_active_production=AsyncMock(),
        list_by_status=AsyncMock(return_value=[release]),
    )
    validator = PublicRuntimeEnvironmentValidator(repo)

    await validator.validate(release.agent_id, "staging")

    repo.list_by_status.assert_awaited_once_with(
        release.agent_id,
        ReleaseStatus.staging,
    )
