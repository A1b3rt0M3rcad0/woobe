"""Metadata-only verification of explicitly reused portable connections."""
from copy import deepcopy
from uuid import UUID

from sqlalchemy import select

from modules.agent.infra.database.models import ProviderCredentialModel
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
        if (row.provider != connection["provider"] or compile_authentication(row.authentication or {}) != compile_authentication(authentication)
                or any((row.meta or {}).get(key) != value for key, value in (connection.get("metadata") or {}).items())):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        result[alias] = {"credential_id": str(row.id), "provider": row.provider, "existing": True,
            "revision": row.updated_at.isoformat(), "binding_revision": row.binding_revision}
    return result
