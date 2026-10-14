from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from modules.network.infra.services.boundary_service import NetworkBoundaryService
from shared.contracts.project_configuration import ConfigurationError


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["CONFIG_VALUE_MISSING", "CONFIG_VALUE_REVOKED", None])
async def test_native_network_rollback_validates_exact_production_dependencies(monkeypatch, code):
    project, network_id, old_id, current_id = (uuid4() for _ in range(4))
    network = N(id=network_id, project_id=project, production_version_id=current_id)
    now = datetime.now(UTC)
    source = N(id=old_id, network_id=network_id, project_id=project, kind="release",
               created_at=now - timedelta(days=1), resolved_bindings={"root": {"release_id": str(uuid4())}})
    current = N(id=current_id, created_at=now)
    rows = {network_id: network, old_id: source, current_id: current}
    lock = AsyncMock()

    async def get(model, key, **kwargs):
        lock.assert_awaited_once_with(session, project_id=project)
        return rows.get(key)

    session = N(get=AsyncMock(side_effect=get), add=Mock(), flush=AsyncMock())

    @asynccontextmanager
    async def transaction():
        yield session

    session.begin = transaction
    service = object.__new__(NetworkBoundaryService)
    service._session_factory = transaction
    gate = AsyncMock(side_effect=ConfigurationError(code) if code else None)
    monkeypatch.setattr("modules.network.application.configuration_acceptance.prepare_configuration", gate)
    monkeypatch.setattr("modules.network.application.configuration_acceptance.lock_configuration", lock)
    args = dict(network_id=network_id, project_id=project, source_version_id=old_id,
                expected_current_production_version_id=current_id, change_description="Rollback", created_by=None)
    if code:
        with pytest.raises(ConfigurationError) as error:
            await service.activate_production(**args)
        assert error.value.code == code
        assert network.production_version_id == current_id
        session.flush.assert_not_awaited()
    else:
        selected, activation = await service.activate_production(**args)
        assert selected is source and network.production_version_id == old_id
        assert activation.activation_kind == "rollback"
    gate.assert_awaited_once_with(session, project_id=project, environment="production", bindings=source.resolved_bindings)
