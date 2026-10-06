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


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ["workspace", "scope", "condition", "expiration"])
async def test_sql_delegation_policy_rejects_authority_escalation_before_issuance(violation):
    issuing_actor = actor()
    project_id = uuid4()
    expiry = datetime.now(UTC) + timedelta(hours=1)
    issuing_actor.delegation_expires_at = expiry
    grant = SimpleNamespace(permissions=["api_key:write", "run:execute"],
                            conditions={"environments": ["staging"]})
    project_workspace = uuid4() if violation == "workspace" else issuing_actor.workspace_id
    session = SimpleNamespace(bind=None, execute=AsyncMock(side_effect=[result(issuing_actor),
        result("active"), result(project_workspace), result(grant)]))
    scopes = ["traces:read"] if violation == "scope" else ["runtime:execute"]
    conditions = {} if violation == "condition" else {"environments": ["staging"]}
    requested_expiry = None if violation == "expiration" else expiry
    error = NotFoundError if violation == "workspace" else AuthorizationError
    with pytest.raises(error):
        await SqlApiKeyDelegationPolicy(session).validate(actor_key_id=uuid4(),
            project_id=project_id, scopes=scopes, conditions=conditions, expires_at=requested_expiry)
    if violation == "workspace":
        assert session.execute.await_count == 3
    session.execute = AsyncMock(side_effect=[result(issuing_actor), result("active"),
        result(issuing_actor.workspace_id), result(grant)])
    assert await SqlApiKeyDelegationPolicy(session).validate(actor_key_id=uuid4(),
        project_id=project_id, scopes=["runtime:execute"], conditions={"environments": ["staging"]},
        expires_at=expiry) == expiry
