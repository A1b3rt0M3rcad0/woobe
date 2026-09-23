from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.infra.database.models import NetworkSessionModel, NetworkVersionModel
from modules.network.infra.services.service import NetworkApplicationService
from shared.infra.errors import ConflictError


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Session:
    def __init__(self, network_session, version) -> None:
        self.network_session = network_session
        self.version = version
        self.get_calls: list[tuple[object, object, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return _Transaction()

    async def get(self, model, identity, **kwargs):
        self.get_calls.append((model, identity, kwargs))
        if model is NetworkSessionModel:
            return self.network_session
        if model is NetworkVersionModel:
            return self.version
        return None

    async def scalar(self, _statement):
        return None


class _SessionFactory:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return self.session


@pytest.mark.asyncio
async def test_network_service_locks_session_and_rejects_fixed_external_context_field() -> None:
    project_id = uuid4()
    network_id = uuid4()
    session_id = uuid4()
    version_id = uuid4()
    network_session = SimpleNamespace(
        id=session_id,
        network_id=network_id,
        project_id=project_id,
        status="active",
        environment="production",
        network_version_id=version_id,
        external_context_snapshot={"client_id": "client-123"},
    )
    version = SimpleNamespace(
        network_id=network_id,
        project_id=project_id,
        version="v1",
        composition_hash="hash",
        definition={},
        resolved_bindings={},
        effective_external_context_contract={
            "client_id": {
                "schema": {"type": "string"},
                "scope": "session",
                "consumers": {"support": {"required": True}},
            }
        },
    )
    db = _Session(network_session, version)
    service = NetworkApplicationService.__new__(NetworkApplicationService)
    service._session_factory = _SessionFactory(db)
    service._run_storage_version = "legacy"
    service._definition = lambda _value: SimpleNamespace()

    with pytest.raises(ConflictError) as exc_info:
        await service.submit_execution(
            network_id=network_id,
            project_id=project_id,
            network_session_id=session_id,
            message="hello",
            external_context={"client_id": "other-client"},
            idempotency_key=None,
        )

    error = exc_info.value
    assert error.code == "EXTERNAL_CONTEXT_SESSION_FIELD_ALREADY_SET"
    assert error.fields == ["client_id"]
    assert error.scope == "session"
    assert error.reason == "already_set"

    session_reads = [
        call for call in db.get_calls if call[0] is NetworkSessionModel
    ]
    assert len(session_reads) == 1
    assert session_reads[0][2].get("with_for_update") is True
