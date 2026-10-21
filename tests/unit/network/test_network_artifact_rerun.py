from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.infra.database.models import NetworkExecutionModel, NetworkSessionModel
from modules.network.infra.services.rerun_service import NetworkRerunService


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class _Session:
    def __init__(self, source, network_session):
        self.source = source
        self.network_session = network_session
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def begin(self):
        return _Transaction()

    async def get(self, model, _identity, **_kwargs):
        if model is NetworkExecutionModel:
            return self.source
        if model is NetworkSessionModel:
            return self.network_session
        return None

    async def scalar(self, _statement):
        return None

    def add(self, value):
        self.added.append(value)

    def add_all(self, values):
        self.added.extend(values)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_network_rerun_preserves_private_workspace_and_principal_binding(monkeypatch):
    project_id, network_id, session_id, execution_id = [uuid4() for _ in range(4)]
    binding = {
        "schema_version": 1,
        "workspace_id": "workspace-rerun",
        "catalog_version": 17,
        "binding_scope": "session",
        "actions": ["read"],
    }
    principal = {"kind": "runtime", "project_id": str(project_id)}
    source = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        network_id=network_id,
        network_version_id=None,
        network_session_id=session_id,
        status="completed",
        idempotency_key=None,
        input_message="continue",
        draft_revision=3,
        definition_snapshot={"nodes": []},
        resolved_bindings_snapshot={"node": {"snapshot_override": {}}},
        external_context_snapshot={"workspace_key": "customer-42"},
        artifact_workspace_binding=binding,
        runtime_principal_snapshot=principal,
    )
    network_session = SimpleNamespace(status="active", environment="draft", last_message_at=None)
    session = _Session(source, network_session)

    async def lock_configuration(_session, **_kwargs):
        return None

    async def accept_configuration(_session, **_kwargs):
        return None

    monkeypatch.setattr(
        "modules.network.application.configuration_acceptance.lock_configuration",
        lock_configuration,
    )
    monkeypatch.setattr(
        "modules.network.application.configuration_acceptance.accept_configuration",
        accept_configuration,
    )
    service = NetworkRerunService(lambda: session)
    rerun = await service.execute(
        execution_id=execution_id,
        project_id=project_id,
    )

    assert rerun.artifact_workspace_binding == binding
    assert rerun.runtime_principal_snapshot == principal
    assert rerun.external_context_snapshot == source.external_context_snapshot
    assert rerun.artifact_workspace_binding is not binding
    assert rerun.runtime_principal_snapshot is not principal
