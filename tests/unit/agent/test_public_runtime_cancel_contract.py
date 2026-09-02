from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import public_runtime_routes
from shared.infra.errors import AuthorizationError
from shared.presentation.http.response import Response
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
async def test_public_cancel_dispatches_agent_run_without_network_call(monkeypatch) -> None:
    run_id = uuid4()
    principal = _runtime_principal("agent")
    agent_calls = []
    network_composer_calls = []

    async def cancel_agent(actual_run_id, request):
        agent_calls.append((actual_run_id, request))
        return {"run_id": str(actual_run_id), "status": "cancel_requested"}

    def cancel_network_composer():
        network_composer_calls.append(True)
        return object()

    monkeypatch.setattr(public_runtime_routes, "cancel_agent_run", cancel_agent)
    monkeypatch.setattr(
        public_runtime_routes,
        "cancel_runtime_network_execution_composer",
        cancel_network_composer,
    )
    request = _request(principal)

    response = await public_runtime_routes.cancel_run(run_id, request)

    assert response == {"run_id": str(run_id), "status": "cancel_requested"}
    assert agent_calls == [(run_id, request)]
    assert network_composer_calls == []


@pytest.mark.asyncio
async def test_public_cancel_dispatches_network_run_without_agent_call(monkeypatch) -> None:
    run_id = uuid4()
    principal = _runtime_principal("network")
    agent_calls = []
    handler = object()
    adapter_calls = []

    async def cancel_agent(actual_run_id, request):
        agent_calls.append((actual_run_id, request))
        return {"run_id": str(actual_run_id)}

    async def adapt(request, actual_handler):
        adapter_calls.append((request, actual_handler))
        return Response(
            status_code=202,
            body={
                "success": True,
                "data": {"run_id": str(run_id), "status": "cancel_requested"},
            },
        )

    monkeypatch.setattr(public_runtime_routes, "cancel_agent_run", cancel_agent)
    monkeypatch.setattr(
        public_runtime_routes,
        "cancel_runtime_network_execution_composer",
        lambda: handler,
    )
    monkeypatch.setattr(public_runtime_routes, "request_adapter", adapt)
    monkeypatch.setattr(public_runtime_routes, "response_adapter", lambda response: response.body)
    request = _request(principal)

    response = await public_runtime_routes.cancel_run(run_id, request)

    assert response["data"]["run_id"] == str(run_id)
    assert response["data"]["status"] == "cancel_requested"
    assert adapter_calls == [(request, handler)]
    assert agent_calls == []


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
async def test_public_reattach_dispatch_matches_same_runtime_target_contract(monkeypatch) -> None:
    run_id = uuid4()
    agent_principal = _runtime_principal("agent")
    network_principal = _runtime_principal("network")
    calls = []

    async def attach_agent(actual_run_id, request):
        calls.append(("agent", actual_run_id, request))
        return "agent-stream"

    async def attach_network(actual_run_id, request):
        calls.append(("network", actual_run_id, request))
        return "network-stream"

    monkeypatch.setattr(public_runtime_routes, "attach_agent_run", attach_agent)
    monkeypatch.setattr(
        public_runtime_routes,
        "attach_network_run_composer",
        lambda: attach_network,
    )

    assert await public_runtime_routes.reattach_run(run_id, _request(agent_principal)) == "agent-stream"
    assert await public_runtime_routes.reattach_run(run_id, _request(network_principal)) == "network-stream"
    assert [item[0] for item in calls] == ["agent", "network"]


@pytest.mark.asyncio
async def test_public_active_run_dispatch_matches_runtime_target(monkeypatch) -> None:
    session_id = uuid4()
    agent_principal = _runtime_principal("agent")
    network_principal = _runtime_principal("network")
    calls = []

    async def active_agent(request, *, session_id):
        calls.append(("agent", session_id, request))
        return "agent-active"

    async def active_network(request, *, network_session_id, **_kwargs):
        calls.append(("network", network_session_id, request))
        return "network-active"

    monkeypatch.setattr(public_runtime_routes, "active_agent_run", active_agent)
    monkeypatch.setattr(
        public_runtime_routes,
        "active_network_run_composer",
        lambda: active_network,
    )

    assert await public_runtime_routes.active_session_run(session_id, _request(agent_principal)) == "agent-active"
    assert await public_runtime_routes.active_session_run(session_id, _request(network_principal)) == "network-active"
    assert [item[0] for item in calls] == ["agent", "network"]
