from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.identity.infra.services.session_lifecycle import IssuedSession, SessionLifecycle
from shared.infra.errors import AuthenticationError
from shared.security.refresh_tokens import hash_refresh_token


@pytest.mark.asyncio
async def test_rotate_records_replacement_session_lineage_without_revoking_access_session() -> None:
    user_id = uuid4()
    session_id = uuid4()
    replacement_id = uuid4()
    secret = "refresh-secret"
    current = SimpleNamespace(
        user_id=user_id,
        refresh_token_hash=hash_refresh_token(secret),
        revoked_at=None,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        replaced_by_session_id=None,
        last_used_at=None,
        updated_at=None,
    )
    uow = SimpleNamespace(
        session=SimpleNamespace(get=AsyncMock(return_value=current)),
    )
    lifecycle = SessionLifecycle(ttl_days=30)
    lifecycle.issue = AsyncMock(
        return_value=IssuedSession(
            id=replacement_id,
            user_id=user_id,
            secret="new-refresh-secret",
        )
    )

    result = await lifecycle.rotate(
        uow,
        session_id=session_id,
        secret=secret,
        user_agent="pytest",
        ip_address="127.0.0.1",
    )

    assert result.id == replacement_id
    assert current.revoked_at is None
    assert current.replaced_by_session_id == replacement_id
    lifecycle.issue.assert_awaited_once_with(
        uow,
        user_id=user_id,
        user_agent="pytest",
        ip_address="127.0.0.1",
    )


@pytest.mark.asyncio
async def test_rotate_detects_reuse_from_replacement_lineage() -> None:
    user_id = uuid4()
    session_id = uuid4()
    replacement_id = uuid4()
    secret = "refresh-secret"
    current = SimpleNamespace(
        user_id=user_id,
        refresh_token_hash=hash_refresh_token(secret),
        revoked_at=None,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        replaced_by_session_id=replacement_id,
        last_used_at=None,
        updated_at=None,
    )
    uow = SimpleNamespace(
        session=SimpleNamespace(get=AsyncMock(return_value=current)),
        commit=AsyncMock(),
    )
    lifecycle = SessionLifecycle(ttl_days=30)
    lifecycle.issue = AsyncMock()
    lifecycle.revoke_all = AsyncMock()

    with pytest.raises(AuthenticationError, match="Refresh session reuse detected"):
        await lifecycle.rotate(
            uow,
            session_id=session_id,
            secret=secret,
            user_agent="pytest",
            ip_address="127.0.0.1",
        )

    lifecycle.revoke_all.assert_awaited_once_with(uow, user_id)
    uow.commit.assert_awaited_once_with()
    lifecycle.issue.assert_not_awaited()

