"""Owner-controlled Provider cutover; invoked by the authorized migration job."""
from sqlalchemy import select, update
from modules.agent.application.interfaces.project_configuration import configuration_for_session
from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.mappers import provider_credential_model_to_entity
from modules.agent.infra.adapters.configuration_bindings import provider_destination
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError


async def inventory_provider_configuration(session, *, project_id, after_id=None, limit=100):
    """Keyset inventory reads metadata only; no ciphertext enters the report."""
    from types import SimpleNamespace
    statement = select(ProviderCredentialModel.id, ProviderCredentialModel.provider,
        ProviderCredentialModel.updated_at, ProviderCredentialModel.meta).where(
        ProviderCredentialModel.project_id == project_id, ProviderCredentialModel.authentication.is_(None))
    if after_id is not None:
        statement = statement.where(ProviderCredentialModel.id > after_id)
    rows = (await session.execute(statement.order_by(ProviderCredentialModel.id).limit(limit + 1))).all()
    items = []
    for row in rows[:limit]:
        item = {"kind": "provider_credential", "id": str(row.id), "revision": row.updated_at.isoformat(), "state": "eligible"}
        try:
            destination = provider_destination(SimpleNamespace(provider=row.provider, metadata=row.meta))
            # The central planner validates destinations before returning this
            # internal projection or persisting it. Never expose it directly.
            item["destinations"] = [destination]
        except ConfigurationError as error:
            item.update(state="blocked", code=error.code, destinations=[])
        items.append(item)
    return {"items": items, "next_after": str(rows[limit - 1].id) if len(rows) > limit else None}


async def migrate_provider_configuration(session, *, project_id, credential_id, expected_revision, destinations,
                                         required_processes, actor):
    configuration = configuration_for_session(session)
    if configuration is None:
        raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
    await configuration.require_bridge(required_processes=required_processes)
    row = await session.scalar(select(ProviderCredentialModel).where(ProviderCredentialModel.id == credential_id,
        ProviderCredentialModel.project_id == project_id).with_for_update())
    if row is None:
        raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
    if row.authentication is not None:
        reference = (row.authentication.get('fields') or {}).get('api_key') or {}
        if reference.get('source') == 'legacy_configuration':
            return {'id': str(row.id), 'state': 'cutover', 'unchanged': True}
        return {'id': str(row.id), 'state': 'native_reference', 'unchanged': True}
    if row.updated_at.isoformat() != expected_revision:
        raise ConfigurationError('CONFIG_REVISION_CONFLICT')
    if not destinations:
        raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
    # The migration planner supplies destinations captured from retained native
    # consumers. Never derive an arbitrary wildcard or grant future destinations.
    credential = provider_credential_model_to_entity(row)
    destination = provider_destination(credential)
    if destination not in destinations:
        raise ConfigurationError('CONFIG_DESTINATION_CHANGED')
    field = '/authentication/fields/api_key'
    dependencies = [ConfigurationDependency(project_id, 'provider_credential', credential_id,
        expected_revision, field, 'pending', item) for item in sorted(set(destinations))]
    result = await configuration.adopt(project_id=project_id, source_kind='provider_credential', source_id=credential_id,
        field_path=field, source_revision=expected_revision, encrypted_value=row.encrypted_secret,
        dependencies=dependencies, actor=actor)
    if result['phase'] not in {'cutover', 'completed'}:
        raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
    authentication = {'type': 'api_key', 'fields': {'api_key': {'source': 'legacy_configuration', 'key': result['key'], 'alias_id': result['alias_id']}}}
    # Storage migration is not a semantic credential edit. Preserve old revision
    # evidence and identity; source clearing and alias creation share this commit.
    await session.execute(update(ProviderCredentialModel).where(ProviderCredentialModel.id == row.id).values(
        authentication=authentication, encrypted_secret=None, updated_at=row.updated_at))
    await session.flush()
    return {'id': str(row.id), 'key': result['key'], 'alias_id': result['alias_id'], 'state': result['phase'], 'material': result['state'], 'unchanged': False}
