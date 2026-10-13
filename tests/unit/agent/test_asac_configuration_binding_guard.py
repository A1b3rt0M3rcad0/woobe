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


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_provider_binding_route_remains_exact_at_activation(monkeypatch, legacy):
    import modules.agent.infra.database.asac_binding_guard as module
    monkeypatch.setattr(module, "authorize_export_read", AsyncMock())
    reference = {"source": "project_environment", "key": "PRIMARY_KEY"}
    if legacy:
        reference = {"source": "legacy_configuration", "key": "PRIMARY_KEY", "alias_id": str(uuid4())}
    row = N(id=uuid4(), provider="openai", status="active", updated_at=datetime.now(UTC), binding_revision=5,
        authentication={"type": "api_key", "fields": {"api_key": reference}})
    evidence = {"credential_id": str(row.id), "provider": row.provider, "binding_revision":5, "existing":True,
        "binding_source": "legacy_configuration" if legacy else "project_environment"}
    environment = N(verify=AsyncMock())
    guard = AgentASaCBindingGuard(environment)
    arguments = dict(project_id=uuid4(), resource_id=uuid4(), principal=object(), environment="production",
        expected={"credentials":{"primary":evidence}})
    await guard.verify(N(scalar=AsyncMock(return_value=row)), **arguments)
    evidence['binding_source'] = 'project_environment' if legacy else 'legacy_configuration'
    with pytest.raises(ConflictError, match='credential version'):
        await guard.verify(N(scalar=AsyncMock(return_value=row)), **arguments)
