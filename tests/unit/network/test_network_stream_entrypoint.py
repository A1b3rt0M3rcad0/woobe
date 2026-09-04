from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.entrypoint import RunNetworkRequest
from woobe_api.http.network import runtime_routes as routes


@pytest.mark.asyncio
async def test_create_and_observe_switches_immediately_to_canonical_run_stream(
    monkeypatch,
) -> None:
    network_id = uuid4()
    project_id = uuid4()
    session_id = uuid4()
    execution_id = uuid4()
    execution = SimpleNamespace(id=execution_id)
    sentinel = object()
    submitted: dict[str, object] = {}

    class Service:
        async def submit_execution(self, **kwargs):
            submitted.update(kwargs)
            return execution

    monkeypatch.setattr(routes, "_authorize_project", lambda request, value: None)
    monkeypatch.setattr(routes, "_service", lambda request: Service())

    async def reattach(value, request):
        assert value == execution_id
        return sentinel

    monkeypatch.setattr(routes, "reattach_network_execution", reattach)

    payload = RunNetworkRequest(
        project_id=project_id,
        network_session_id=session_id,
        message="hello",
        idempotency_key="stable-key",
        expected_draft_revision=4,
    )
    result = await routes.run_network_stream(
        network_id,
        payload,
        SimpleNamespace(),
        last_event_id="125",
    )

    assert result is sentinel
    assert submitted == {
        "network_id": network_id,
        "project_id": project_id,
        "network_session_id": session_id,
        "message": "hello",
        "idempotency_key": "stable-key",
        "expected_draft_revision": 4,
    }
