from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shared.contracts.errors import AuthorizationError
from shared.infra.transactional_handler import TransactionalHandler
from shared.presentation.contracts import OperationRequest, OperationResult
from shared.security.principal import ControlPlanePrincipal


@pytest.mark.asyncio
@pytest.mark.parametrize('allowed', [False, True])
async def test_owner_transaction_checks_all_global_material_environments_without_http(monkeypatch, allowed):
    principal = ControlPlanePrincipal(api_key_id=uuid4(), credential_id=uuid4(), workspace_id=uuid4(),
        key_prefix='synthetic', authenticated_at=datetime.now(UTC))
    checked = []

    async def authorize(**identity):
        environment = identity['path_params']['environment']
        checked.append(environment)
        if not allowed and environment != 'staging':
            raise AuthorizationError('Not authorized for this Environment')

    authorizer = SimpleNamespace(require_active_control=AsyncMock(), authorize_control_key=authorize)
    monkeypatch.setattr('shared.security.tenancy.TenantAuthorizer', lambda _: authorizer)
    session = AsyncSession()
    class Uow:
        async def __aenter__(self):
            self.session = session
            return self
        async def __aexit__(self, *args):
            await session.close()
    handler = AsyncMock(return_value=OperationResult(body={'success': True}))
    request = OperationRequest(principal=principal, body={'environment': 'staging'},
        path_params={'project_id': uuid4()}, metadata={})
    operation = TransactionalHandler(Uow(), handler,
        additional_permissions=lambda _: [('project:environment:value:write', 'tool:write')])
    if allowed:
        await operation(request)
        assert checked == ['draft', 'staging', 'production']
        handler.assert_awaited_once()
    else:
        with pytest.raises(AuthorizationError):
            await operation(request)
        handler.assert_not_awaited()
