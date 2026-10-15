"""Deletion eligibility and edits use the same real configuration transactions."""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from modules.core.infra.database.configuration_models import ConfigurationLeaseModel
from shared.contracts.project_configuration import ConfigurationError
from tests.integration.core.test_project_configuration_postgres import (
    CANARY, configuration as configuration, prepared,
)


@pytest.mark.asyncio
async def test_deletion_preview_rechecks_new_usage_and_keeps_used_keys_editable(configuration, monkeypatch):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    from modules.core.infra.database import configuration_store
    monkeypatch.setattr(configuration_store, 'decrypt_secret', lambda *_: pytest.fail('Deletion checks must not decrypt values'))
    preview = await store.deletion_check(project_id=project, key_id=key, environment='staging')
    assert preview['can_delete'] and preview['scope'] == 'all_environments'
    assert not any(preview['blockers'].values())
    # A dependency can arrive between preview and confirmation.
    await store.register_references([dep])
    blocked = await store.deletion_check(project_id=project, key_id=key, environment='production')
    assert not blocked['can_delete'] and blocked['blockers']['retained_resources']
    with pytest.raises(ConfigurationError) as error:
        await store.remove_key(project_id=project, key_id=key, expected_revision=preview['definition_revision'], actor='owner')
    assert error.value.code == 'CONFIG_REFERENCE_IN_USE'
    edited = await store.patch(project_id=project, key_id=key, expected_revision=1,
        changes={'description': 'Still editable while in use'}, actor='owner')
    assert edited['id'] == str(key) and edited['definition_revision'] == 2
    await store.write_value(project_id=project, key_id=key, environment='staging', expected_revision=0, value=CANARY)
    with pytest.raises(ConfigurationError) as other_project:
        await store.deletion_check(project_id=uuid4(), key_id=key, environment='draft')
    assert other_project.value.code == 'CONFIG_REFERENCE_NOT_FOUND'


@pytest.mark.asyncio
async def test_deletion_preview_protects_legacy_bindings_without_exposing_values(configuration):
    from modules.core.infra.database.configuration_models import LegacyConfigurationAliasModel
    store, project, _ = configuration
    declared = await store.declare(project_id=project, key='LEGACY_PREVIEW')
    key_id = UUID(declared['id'])
    store.session.add(LegacyConfigurationAliasModel(project_id=project, key_id=key_id,
        source_kind='provider_credential', source_id=uuid4(), field_path='/authentication/fields/api_key',
        source_revision='1', routes={}, state='eligible', revision=1))
    await store.session.flush()
    preview = await store.deletion_check(project_id=project, key_id=key_id, environment='draft')
    assert not preview['can_delete'] and preview['blockers']['legacy_binding']
    assert 'values' not in preview and CANARY not in str(preview)


@pytest.mark.asyncio
async def test_live_run_blocks_preview_but_expired_lease_and_retention_do_not(configuration):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment='draft', value=CANARY, expected_revision=0)
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment='draft', dependencies=[dep])
    await store.write_value(project_id=project, key_id=key, environment='draft', clear=True, expected_revision=1)
    preview = await store.deletion_check(project_id=project, key_id=key, environment='staging')
    assert not preview['can_delete'] and preview['blockers']['active_run']
    lease = await store.session.scalar(select(ConfigurationLeaseModel).where(ConfigurationLeaseModel.run_id == run))
    lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await store.session.flush()
    assert (await store.deletion_check(project_id=project, key_id=key, environment='draft'))['can_delete']
    await store.remove_key(project_id=project, key_id=key, expected_revision=1, actor='owner')
