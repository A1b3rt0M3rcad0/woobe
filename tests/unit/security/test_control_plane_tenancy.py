from uuid import uuid4

import pytest



from starlette.requests import Request

from shared.infra.errors import AuthorizationError
from shared.security.tenancy import TenantAuthorizer
from woobe_api.security.http_guard import HttpSecurityGuard


def test_access_project_id_is_treated_as_project_context() -> None:
    project_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"access_project_id": project_id},
        {},
        {},
    )

    assert identifiers == [("access_project_id", project_id)]


def test_network_id_is_visible_to_tenant_authorization() -> None:
    network_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"network_id": network_id},
        {},
        {},
    )

    assert identifiers == [("network_id", network_id)]


def test_run_id_is_visible_to_tenant_authorization() -> None:
    run_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"run_id": run_id},
        {},
        {},
    )

    assert identifiers == [("run_id", run_id)]


def _request(path: str, query: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query,
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("test", 80),
        }
    )


def test_run_trace_authorization_uses_run_specific_identifier() -> None:
    trace_id = uuid4()

    result = HttpSecurityGuard._authorization_path_params(
        _request(f"/runtime/runs/by-trace/{trace_id}"),
        {"trace_id": str(trace_id)},
    )

    assert result == {"run_trace_id": str(trace_id)}


def test_observability_trace_authorization_keeps_observability_identifier() -> None:
    trace_id = uuid4()

    result = HttpSecurityGuard._authorization_path_params(
        _request(f"/observability/traces/{trace_id}"),
        {"trace_id": str(trace_id)},
    )

    assert result == {"trace_id": str(trace_id)}


def test_agent_session_filter_is_forwarded_to_authority_conditions() -> None:
    agent_id = uuid4()
    path = f"/runtime/agents/{agent_id}/sessions"
    allowed = HttpSecurityGuard._authorization_path_params(
        _request(path, b"environment=staging"), {"agent_id": str(agent_id)}
    )
    assert allowed == {"agent_id": str(agent_id), "environment": "staging"}
    conditions = {
        "environments": ["staging"],
        "target_types": ["agent"],
        "target_ids": [str(agent_id)],
    }
    TenantAuthorizer._require_conditions(
        conditions, permission="run:read", path_context=allowed
    )
    for query in (b"environment=production", b""):
        rejected = HttpSecurityGuard._authorization_path_params(
            _request(path, query), {"agent_id": str(agent_id)}
        )
        with pytest.raises(AuthorizationError):
            TenantAuthorizer._require_conditions(
                conditions, permission="run:read", path_context=rejected
            )


def test_unreviewed_queries_do_not_become_path_authority() -> None:
    agent_id = uuid4()
    original = {"agent_id": str(agent_id)}
    normalized = HttpSecurityGuard._authorization_path_params(
        _request(f"/ai/agents/{agent_id}", b"environment=staging"), original
    )
    assert normalized == original


@pytest.mark.asyncio
async def test_control_authority_rejects_an_expiry_changed_after_authentication():
    from datetime import UTC, datetime, timedelta
    from unittest.mock import AsyncMock, Mock
    from types import SimpleNamespace
    import pytest
    from shared.security.principal import ControlPlanePrincipal
    from shared.contracts.errors import AuthenticationError
    expiry = datetime.now(UTC) + timedelta(hours=2)
    actor = ControlPlanePrincipal(api_key_id=uuid4(), credential_id=uuid4(), workspace_id=uuid4(),
        key_prefix="fixture", authenticated_at=datetime.now(UTC), expires_at=expiry,
        permissions=frozenset({"keys:create"}))
    row = {"status": "active", "revoked_at": None, "workspace_status": "active",
           "expires_at": expiry - timedelta(hours=1), "permissions": ["keys:create"],
           "on_project_create_permissions": [], "delegation_expires_at": None}
    result = Mock()
    result.mappings.return_value.first.return_value = row
    session = SimpleNamespace(bind=None, execute=AsyncMock(return_value=result))
    with pytest.raises(AuthenticationError, match="retry authentication"):
        await TenantAuthorizer(session).require_active_control(actor)
    row["expires_at"] = expiry
    await TenantAuthorizer(session).require_active_control(actor)


@pytest.mark.asyncio
async def test_control_authority_rejects_changed_delegation_ceiling():
    from datetime import UTC, datetime, timedelta
    from unittest.mock import AsyncMock, Mock
    from types import SimpleNamespace
    from shared.security.principal import ControlPlanePrincipal
    from shared.contracts.errors import AuthenticationError
    ceiling = datetime.now(UTC) + timedelta(hours=2)
    actor = ControlPlanePrincipal(api_key_id=uuid4(), credential_id=uuid4(), workspace_id=uuid4(),
        key_prefix="fixture", authenticated_at=datetime.now(UTC), delegation_expires_at=ceiling)
    row = {"status": "active", "revoked_at": None, "workspace_status": "active",
           "expires_at": None, "permissions": [], "on_project_create_permissions": [],
           "delegation_expires_at": ceiling - timedelta(hours=1)}
    result = Mock()
    result.mappings.return_value.first.return_value = row
    session = SimpleNamespace(bind=None, execute=AsyncMock(return_value=result))
    with pytest.raises(AuthenticationError, match="retry authentication"):
        await TenantAuthorizer(session).require_active_control(actor)
    row["delegation_expires_at"] = ceiling.isoformat()
    await TenantAuthorizer(session).require_active_control(actor)
