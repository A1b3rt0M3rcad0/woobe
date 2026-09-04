from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.infra.security import SqlSecurityAuthenticator
from shared.security.principal import AuthenticatedPrincipal


@pytest.mark.asyncio
async def test_active_session_validation_uses_identity_user_sessions() -> None:
    user_id = uuid4()
    session_id = uuid4()
    principal = AuthenticatedPrincipal(
        user_id=user_id,
        session_id=session_id,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    result = SimpleNamespace(
        one_or_none=lambda: (
            user_id,
            None,
            datetime.now(UTC) + timedelta(days=30),
        )
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    authenticator = SqlSecurityAuthenticator.__new__(SqlSecurityAuthenticator)

    await authenticator._require_active_session(session, principal)

    statement = str(session.execute.await_args.args[0])
    params = session.execute.await_args.args[1]
    assert "identity.user_sessions" in statement
    assert "identity.refresh_sessions" not in statement
    assert params == {"session_id": session_id}
