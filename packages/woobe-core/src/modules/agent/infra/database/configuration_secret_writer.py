"""A new legacy Secret has one central material authority from its first commit."""
from modules.agent.application.interfaces.project_configuration import configuration_for_session
from shared.contracts.project_configuration import ConfigurationError


async def centralize_new_secret(session, secret):
    if secret.configuration_reference is not None:
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    store = configuration_for_session(session)
    if store is None:
        raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
    result = await store.adopt(project_id=secret.project_id, source_kind='secret', source_id=secret.id,
        field_path='/value', source_revision='legacy-create:' + str(secret.id), encrypted_value=secret.encrypted_value,
        dependencies=[], actor='legacy-secret-create')
    if result['phase'] not in {'cutover', 'completed'}:
        raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
    secret.configuration_reference = {'source':'legacy_configuration', 'key':result['key'], 'alias_id':result['alias_id']}
    secret.encrypted_value = ''
