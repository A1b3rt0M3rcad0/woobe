from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.security.tenancy import TenantAuthorizer


@pytest.mark.asyncio
@pytest.mark.parametrize('context,granted,permission', [
    ({}, {'tool:write'}, 'project:environment:validate'),
    ({'environment': 'staging'}, {'tool:write'}, 'project:environment:validate'),
    ({'environment': 'production'}, {'tool:write'}, 'project:environment:validate'),
    ({'tool_id': None}, {'tool:write'}, 'project:environment:validate'),
    ({'_configuration_legacy_operation': 'new.configuration.test'}, {'tool:write'}, 'project:environment:validate'),
    ({}, set(), 'project:environment:validate'),
    ({}, {'tool:write'}, 'project:environment:bind'),
    ({}, {'tool:write'}, 'project:environment:use-policy:write'),
])
async def test_legacy_refresh_marker_cannot_expand_current_authority(context, granted, permission):
    session = AsyncMock()
    context = {'_configuration_legacy_permission': 'tool:write',
               '_configuration_legacy_operation': 'mcp.refresh', 'environment': 'draft',
               'tool_id': uuid4(), **context}
    # The empty-context case remains denied when no captured record exists.
    session.scalar.return_value = None
    assert not await TenantAuthorizer(session)._legacy_configuration_write(project_id=uuid4(),
        subject_type='control_key', subject_id=uuid4(), required_permission=permission,
        granted=granted, path_context=context)


@pytest.mark.asyncio
async def test_translation_requires_exact_captured_catalog_revision():
    session = AsyncMock(); session.scalar.return_value = 1
    assert await TenantAuthorizer(session)._legacy_configuration_write(project_id=uuid4(),
        subject_type='human', subject_id=uuid4(), required_permission='project:environment:validate',
        granted={'tool:write'}, path_context={'_configuration_legacy_permission': 'tool:write',
            '_configuration_legacy_operation': 'mcp.refresh', 'environment': 'draft', 'tool_id': uuid4()})
    statement, params = session.scalar.await_args.args
    assert "catalog_revision='pre-project_configuration.v1'" in str(statement)
    assert params['permission'] == 'tool:write' and params['subject_type'] == 'human'
