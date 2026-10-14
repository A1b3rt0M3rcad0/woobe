"""Metadata-only verification of explicitly reused portable connections."""
from copy import deepcopy
from uuid import UUID

from sqlalchemy import select

from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.application.interfaces.project_configuration import configuration_for_session
from shared.contracts.project_configuration import ConfigurationError, compile_authentication


async def inspect_configuration_provider_reuse(session, *, project_id, connections, bindings, configuration):
    identifiers = {UUID(value["credential_id"]) for value in bindings.values() if value.get("credential_id")}
    rows = (await session.execute(select(ProviderCredentialModel.id, ProviderCredentialModel.provider,
        ProviderCredentialModel.meta, ProviderCredentialModel.authentication, ProviderCredentialModel.binding_revision,
        ProviderCredentialModel.updated_at, ProviderCredentialModel.status).where(
        ProviderCredentialModel.project_id == project_id, ProviderCredentialModel.id.in_(identifiers)))).all()
    by_id = {row.id: row for row in rows}
    result = {}
    for alias, binding in bindings.items():
        connection = connections[alias]
        if binding.get("create"):
            result[alias] = {"provider": connection["provider"], "existing": False}
            continue
        row = by_id.get(UUID(binding["credential_id"]))
        if row is None or row.status != "active":
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        authentication = deepcopy(connection["authentication"])
        for reference in authentication["fields"].values():
            reference["key"] = configuration[reference["key"]]["key"]
        actual = compile_authentication(row.authentication or {}, allow_legacy=True)
        legacy = False
        for field, reference in actual['fields'].items():
            if reference['source'] != 'legacy_configuration':
                continue
            # An explicit native credential binding preserves that connection's
            # compatibility route. It never converts a generic key lookup into
            # an alias lookup, grants a new consumer or changes stored auth.
            store = configuration_for_session(session)
            if store is None:
                raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
            owned = await store.legacy_reference(project_id=project_id, source_kind='provider_credential',
                source_id=row.id, field_path='/authentication/fields/' + field)
            if owned != reference:
                raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
            actual['fields'][field] = {'source': 'project_environment', 'key': reference['key']}
            legacy = True
        if (row.provider != connection["provider"] or actual != compile_authentication(authentication)
                or any((row.meta or {}).get(key) != value for key, value in (connection.get("metadata") or {}).items())):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        result[alias] = {"credential_id": str(row.id), "provider": row.provider, "existing": True,
            "binding_revision": row.binding_revision,
            "binding_source": "legacy_configuration" if legacy else "project_environment"}
    return result
