from modules.core.infra.database.configuration_resolution import ConfigurationResolution


class ConfigurationRuntimeResolver:
    def __init__(self, session_factory, *, encryption_key, consumer_verifier):
        self.consumer_verifier = consumer_verifier
        self.session_factory, self.encryption_key = session_factory, encryption_key

    async def __call__(self, **identity):
        async with self.session_factory() as session:
            await self.consumer_verifier(session, project_id=identity["project_id"], consumer_kind=identity["consumer_kind"], consumer_id=identity["consumer_id"])
            return await ConfigurationResolution(session, encryption_key=self.encryption_key).resolve(**identity)


class OperationConfigurationRuntimeResolver:
    """Resolve only the snapshot returned by a trusted accepted-operation reader."""
    def __init__(self, session_factory, *, encryption_key, operation_verifier):
        if not callable(operation_verifier):
            raise TypeError('Accepted operation verifier is required')
        self.session_factory, self.encryption_key = session_factory, encryption_key
        self.operation_verifier = operation_verifier

    async def __call__(self, *, project_id, operation_kind, operation_id, consumer_kind,
                       consumer_id, field_path, destination):
        from shared.contracts.project_configuration import ConfigurationError
        from shared.runtime_environment import normalize_runtime_environment
        snapshot = await self.operation_verifier(project_id=project_id,
            operation_kind=operation_kind, operation_id=operation_id)
        if (not isinstance(snapshot, dict) or snapshot.get('project_id') != str(project_id)
            or snapshot.get('operation_kind') != operation_kind or snapshot.get('operation_id') != str(operation_id)):
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        try:
            environment = normalize_runtime_environment(snapshot['environment'])
            pins, definitions = snapshot['pins'], snapshot['definitions']
            if not isinstance(pins, list) or not pins or len(pins) > 16 or not isinstance(definitions, list):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED') from None
        async with self.session_factory() as session:
            return await ConfigurationResolution(session, encryption_key=self.encryption_key).resolve_operation_material(
                project_id=project_id, environment=environment, pins=pins, definitions=definitions,
                consumer_kind=consumer_kind, consumer_id=consumer_id, field_path=field_path, destination=destination)
