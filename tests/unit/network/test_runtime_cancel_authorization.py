from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.presentation.reattach_routes import _authorize_execution
from shared.infra.errors import AuthorizationError, NotFoundError
from shared.security.principal import ProjectApiPrincipal


def _execution():
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        network_id=uuid4(),
        network_session_id=uuid4(),
        status="running",
    )


def _network_session(execution, *, environment="production"):
    return SimpleNamespace(
        id=execution.network_session_id,
        environment=environment,
    )


def _principal(execution, **overrides):
    values = {
        "api_key_id": uuid4(),
        "project_id": execution.project_id,
        "key_prefix": "rai_live_network",
        "scopes": frozenset({"runtime:execute"}),
        "kind": "runtime",
        "target_type": "network",
        "target_id": execution.network_id,
        "environment": "production",
        "interfaces": frozenset({"http", "stream"}),
        "authenticated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ProjectApiPrincipal(**values)


def _request(principal):
    return SimpleNamespace(state=SimpleNamespace(principal=principal))


@pytest.mark.asyncio
async def test_network_runtime_cancel_authorizes_exact_target_and_environment() -> None:
    execution = _execution()

    await _authorize_execution(
        _request(_principal(execution)),
        execution,
        _network_session(execution),
    )


@pytest.mark.asyncio
async def test_network_runtime_cancel_rejects_runtime_key_from_another_project() -> None:
    execution = _execution()

    with pytest.raises(AuthorizationError):
        await _authorize_execution(
            _request(_principal(execution, project_id=uuid4())),
            execution,
            _network_session(execution),
        )


@pytest.mark.asyncio
async def test_network_runtime_cancel_hides_execution_from_wrong_target() -> None:
    execution = _execution()

    with pytest.raises(NotFoundError):
        await _authorize_execution(
            _request(_principal(execution, target_id=uuid4())),
            execution,
            _network_session(execution),
        )


@pytest.mark.asyncio
async def test_network_runtime_cancel_hides_execution_from_wrong_environment() -> None:
    execution = _execution()

    with pytest.raises(NotFoundError):
        await _authorize_execution(
            _request(_principal(execution, environment="staging")),
            execution,
            _network_session(execution, environment="production"),
        )


@pytest.mark.asyncio
async def test_network_runtime_cancel_requires_authentication() -> None:
    execution = _execution()

    with pytest.raises(AuthorizationError):
        await _authorize_execution(
            _request(None),
            execution,
            _network_session(execution),
        )
