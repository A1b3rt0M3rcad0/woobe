from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from modules.core.infra.services.api_key_delegation import SqlApiKeyDelegationPolicy
from shared.contracts.errors import AuthenticationError, AuthorizationError, NotFoundError


def result(value):
    return Mock(scalar_one_or_none=Mock(return_value=value))


def actor():
    return SimpleNamespace(workspace_id=uuid4(), status="active", revoked_at=None,
                           expires_at=None, delegation_expires_at=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [None, "inactive", "archived"])
async def test_runtime_issuance_rechecks_active_workspace_in_transaction(status):
    session = SimpleNamespace(bind=None, execute=AsyncMock(side_effect=[result(actor()), result(status)]))
    with pytest.raises(AuthenticationError, match="workspace is inactive"):
        await SqlApiKeyDelegationPolicy(session).validate(actor_key_id=uuid4(),
            project_id=uuid4(), scopes=["runtime:execute"], conditions={}, expires_at=None)
    assert session.execute.await_count == 2
