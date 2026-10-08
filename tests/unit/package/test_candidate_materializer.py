from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.package.infra import native_materializer as materializer
from shared.presentation.contracts import OperationResult
from shared.security.tenancy import _identifier_values


@pytest.mark.asyncio
async def test_candidate_creation_does_not_authorize_planned_agent_id_as_vector_snapshot(monkeypatch):
    project, agent, snapshot, operation, lease = [uuid4() for _ in range(5)]
    received = []

    class Handler:
        def with_receipt(self, receipt):
            assert receipt.operation_id == operation
            return self

        async def __call__(self, request):
            received.append(request)
            return OperationResult(body={"success": True, "data": {"id": str(snapshot)}})

    monkeypatch.setattr(materializer, "create_candidate_snapshot_composer", Handler)
    monkeypatch.setattr(materializer, "agent_candidate_lifecycle_composer", Handler)
    monkeypatch.setattr(materializer, "compile_imported_agent_inputs", lambda **kwargs: {
        "project_id": str(project), "agent_id": str(agent), "provider": "custom", "model": "sealed"})
    plan = {"mode": "candidate", "inspections": {},
        "source_definition": {"components": {"root": {"kind": "Agent"}}},
        "resource_bindings": {"root": {"kind": "Agent", "resource_id": str(agent)}},
        "candidate": {"candidate_id": str(uuid4()), "snapshot_ids": {"root": str(snapshot)}}}
    work = SimpleNamespace(operation=SimpleNamespace(id=operation, project_id=project, lease_token=lease),
        plan=plan, receipts={}, principal=None)
    result = await materializer.NativePackageMaterializer(encryption_key="test-key").execute_phase(work,
        {"component": "root", "action": "create_candidate_snapshot", "key": "candidate:root", "permission": "agent:version"})
    assert result.body["data"]["id"] == str(snapshot)
    request = received[0]
    assert request.body["candidate_snapshot_id"] == str(snapshot)
    assert "snapshot_id" not in request.body
    assert _identifier_values(request.body) == [("project_id", str(project)), ("agent_id", str(agent))]
    assert request.path_params["environment"] == "staging"
