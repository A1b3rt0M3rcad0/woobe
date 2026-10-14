"""Explicit compatibility use approvals; no public name-to-value lookup."""
from hashlib import sha256
from sqlalchemy import select
from shared.contracts.project_configuration import ConfigurationError
from modules.core.domain.project_configuration import canonical_destination
from modules.core.infra.database.configuration_models import (
    LegacyConfigurationAliasModel as Alias, LegacyConfigurationConsumerModel as Consumer,
    ConfigurationUsePolicyModel as Policy,
)


async def approve_legacy_consumers(store, *, project_id, dependencies, authorize, actor):
    """Host authorizes every new consumer/destination in the source transaction.

    Existing grants (including explicit revocations) are never silently replaced
    by a metadata edit. Only an explicit central policy write can revoke/regrant.
    """
    await store.lock_project(project_id)
    additions=[]
    for dep in dependencies:
        alias=await store.session.get(Alias, dep.legacy_alias_id)
        if (alias is None or alias.project_id!=project_id or alias.source_kind!='secret'
                or dep.project_id!=project_id or dep.consumer_kind!='tool'
                or not dep.field_path.startswith('/config/authentication/fields/')):
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        key=await store.key(project_id,alias.key_id)
        if key.key!=dep.key:
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        captured=await store.session.get(Consumer,(alias.id,dep.consumer_kind,dep.consumer_id,dep.field_path))
        destination=canonical_destination(dep.destination)
        policy=await store.session.scalar(select(Policy).where(Policy.project_id==project_id,
            Policy.key_id==alias.key_id,Policy.consumer_kind==dep.consumer_kind,
            Policy.consumer_scope==str(dep.consumer_id),Policy.destination_id==sha256(destination.encode()).hexdigest()))
        if captured is not None and policy is not None and dep.field_path in policy.field_paths:
            continue
        # This is not preservation of an existing route. Require the caller's
        # current explicit use-policy authority for every compatibility Environment.
        await authorize(dep,alias.source_id)
        if policy is not None:
            # An existing revoked/narrow policy is an operator decision; old
            # clients must not implicitly broaden it while editing a Tool.
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        additions.append((dep,alias.id,alias.key_id,captured is None,destination))
    groups={}
    for dep,alias_id,key_id,new_consumer,destination in additions:
        if new_consumer and await store.session.get(Consumer,(alias_id,dep.consumer_kind,dep.consumer_id,dep.field_path)) is None:
            store.session.add(Consumer(alias_id=alias_id,consumer_kind=dep.consumer_kind,consumer_id=dep.consumer_id,field_path=dep.field_path))
            await store.session.flush()
        groups.setdefault((key_id,dep.consumer_kind,str(dep.consumer_id),destination),set()).add(dep.field_path)
    for (key_id,kind,identifier,destination),fields in groups.items():
        await store.grant_use(project_id=project_id,key_id=key_id,consumer_kind=kind,consumer_scope=identifier,
            destination=destination,environments=['draft','staging','production'],field_paths=sorted(fields),
            expected_revision=0,actor=actor)
    await store.register_references(dependencies)
