from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import public_runtime_routes
from shared.infra.errors import AuthorizationError
from shared.security.principal import ProjectApiPrincipal


def _runtime_principal(target_type: str) -> ProjectApiPrincipal:
    target_id = uuid4()
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=uuid4(),
        key_prefix="rai_live_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        agent_id=target_id if target_type == "agent" else None,
        target_type=target_type,
        target_id=target_id,
        environment="production",
        interfaces=frozenset({"http", "stream"}),
        authenticated_at=datetime.now(UTC),
    )


def _request(principal):
    return SimpleNamespace(state=SimpleNamespace(principal=principal))


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_public_cancel_delegates_runtime_target_to_composition(
    monkeypatch,
    target_type: str,
) -> None:
    run_id = uuid4()
    principal = _runtime_principal(target_type)
    calls = []

    async def cancel(actual_target_type, actual_run_id, request):
        calls.append((actual_target_type, actual_run_id, request))
        return {"run_id": str(actual_run_id), "status": "cancel_requested"}

    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "cancel", cancel)
    request = _request(principal)

    response = await public_runtime_routes.cancel_run(run_id, request)

    assert response == {"run_id": str(run_id), "status": "cancel_requested"}
    assert calls == [(target_type, run_id, request)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "principal",
    [
        None,
        SimpleNamespace(kind="runtime", target_type="agent"),
        ProjectApiPrincipal(
            api_key_id=uuid4(),
            project_id=uuid4(),
            key_prefix="project_key",
            kind="project",
            target_type="agent",
            target_id=uuid4(),
            authenticated_at=datetime.now(UTC),
        ),
        ProjectApiPrincipal(
            api_key_id=uuid4(),
            project_id=uuid4(),
            key_prefix="incomplete",
            kind="runtime",
            target_type=None,
            target_id=None,
            authenticated_at=datetime.now(UTC),
        ),
    ],
)
async def test_public_cancel_requires_complete_runtime_principal(principal) -> None:
    with pytest.raises(AuthorizationError):
        await public_runtime_routes.cancel_run(uuid4(), _request(principal))


@pytest.mark.asyncio
async def test_public_reattach_delegates_same_runtime_target_contract(monkeypatch) -> None:
    run_id = uuid4()
    agent_principal = _runtime_principal("agent")
    network_principal = _runtime_principal("network")
    calls = []

    async def reattach(target_type, actual_run_id, request):
        calls.append((target_type, actual_run_id, request))
        return f"{target_type}-stream"

    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "reattach", reattach)

    assert await public_runtime_routes.reattach_run(run_id, _request(agent_principal)) == "agent-stream"
    assert await public_runtime_routes.reattach_run(run_id, _request(network_principal)) == "network-stream"
    assert [item[0] for item in calls] == ["agent", "network"]


@pytest.mark.asyncio
async def test_public_active_run_delegates_runtime_target_to_composition(monkeypatch) -> None:
    session_id = uuid4()
    agent_principal = _runtime_principal("agent")
    network_principal = _runtime_principal("network")
    calls = []

    async def active(target_type, actual_session_id, request):
        calls.append((target_type, actual_session_id, request))
        return f"{target_type}-active"

    monkeypatch.setattr(public_runtime_routes.RUNTIME_HTTP, "active", active)

    assert await public_runtime_routes.active_session_run(session_id, _request(agent_principal)) == "agent-active"
    assert await public_runtime_routes.active_session_run(session_id, _request(network_principal)) == "network-active"
    assert [item[0] for item in calls] == ["agent", "network"]
