from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from shared.infra.errors import AuthenticationError
from shared.security.principal import AuthenticatedPrincipal
from shared.security.tenancy import TenantAuthorizer


def session_with_rows(rows):
    results = []
    for row in rows:
        result = Mock()
        result.mappings.return_value.first.return_value = row
        results.append(result)
    return SimpleNamespace(bind=None, execute=AsyncMock(side_effect=results))


@pytest.mark.asyncio
async def test_session_rotation_keeps_durable_authority_but_revocation_does_not():
    now, replacement = datetime.now(UTC), uuid4()
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    )
    old = {
        "revoked_at": None,
        "expires_at": now - timedelta(minutes=1),
        "replaced_by_session_id": replacement,
        "status": "active",
    }
    active = {
        "revoked_at": None,
        "expires_at": now + timedelta(hours=1),
        "replaced_by_session_id": None,
        "status": "active",
    }
    session = session_with_rows([old, active])
    await TenantAuthorizer(session).require_active_human(actor)
    assert session.execute.call_args_list[1].args[1]["id"] == replacement
    for unavailable in [
        None,
        dict(active, revoked_at=now),
        dict(active, expires_at=now - timedelta(seconds=1)),
        dict(active, status="inactive"),
    ]:
        with pytest.raises(AuthenticationError):
            await TenantAuthorizer(
                session_with_rows([old, unavailable])
            ).require_active_human(actor)


@pytest.mark.asyncio
async def test_session_lineage_cycle_is_rejected_with_a_bounded_query_count():
    now = datetime.now(UTC)
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    row = {
        "revoked_at": None,
        "expires_at": now + timedelta(hours=1),
        "replaced_by_session_id": actor.session_id,
        "status": "active",
    }
    session = session_with_rows([row])
    with pytest.raises(AuthenticationError):
        await TenantAuthorizer(session).require_active_human(actor)
    assert session.execute.await_count == 1
