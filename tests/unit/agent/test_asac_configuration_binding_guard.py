from datetime import UTC, datetime
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database.asac_binding_guard import AgentASaCBindingGuard
from modules.core.infra.database.asac_binding_reader import ASaCEnvironmentBindingReader
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
async def test_configuration_declaration_is_fenced_without_reading_values():
    project = uuid4()
    row = N(id=uuid4(), key="PRIMARY_KEY", kind="secret", definition_revision=3)
    evidence = {"id":str(row.id), "key":row.key, "kind":row.kind, "definition_revision":3, "existing":True}
    session = N(scalar=AsyncMock(return_value=row), scalars=AsyncMock())
    reader = ASaCEnvironmentBindingReader()
    await reader.verify(session, project_id=project, expected={"primary":evidence})
    session.scalars.assert_not_awaited()  # No all-Environment material fingerprint.
    row.definition_revision = 4
    with pytest.raises(ConflictError, match="declaration differs"):
        await reader.verify(session, project_id=project, expected={"primary":evidence})
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_configuration_provider_revision_is_fenced(monkeypatch):
    import modules.agent.infra.database.asac_binding_guard as module
    monkeypatch.setattr(module, "authorize_export_read", AsyncMock())
    row = N(id=uuid4(), provider="openai", status="active", updated_at=datetime.now(UTC), binding_revision=5)
    evidence = {"credential_id":str(row.id), "provider":row.provider, "binding_revision":5, "existing":True}
    session = N(scalar=AsyncMock(return_value=row))
    environment = N(verify=AsyncMock())
    guard = AgentASaCBindingGuard(environment)
    arguments = dict(project_id=uuid4(), resource_id=uuid4(), principal=object(), environment="production", expected={"credentials":{"primary":evidence}})
    await guard.verify(session, **arguments)
    row.binding_revision = 6
    with pytest.raises(ConflictError, match="credential version"):
        await guard.verify(session, **arguments)
    row.binding_revision=5; row.status="revoked"
    with pytest.raises(ConflictError, match="credential version"):
        await guard.verify(session, **arguments)
