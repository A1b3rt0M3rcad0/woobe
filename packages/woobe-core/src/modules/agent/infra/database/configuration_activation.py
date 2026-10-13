"""Agent-owned exact release closure for authoritative activation checks."""
from modules.agent.application.interfaces.project_configuration import configuration_for_session
from shared.contracts.project_configuration import ConfigurationError


class AgentConfigurationActivation:
    def __init__(self, dependency_reader):
        self.dependency_reader = dependency_reader

    async def lock(self, session, *, project_id):
        store = configuration_for_session(session)
        if store is None:
            raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
        await store.lock_project(project_id)

    async def status(self, session, *, project_id, resource_id, release_id, environment):
        store = configuration_for_session(session)
        if store is None:
            raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
        dependencies = await self.dependency_reader(session, project_id=project_id,
            bindings={str(resource_id): {"agent_id": str(resource_id), "release_id": str(release_id)}})
        result, _pins = await store.inspect(project_id=project_id, environment=environment, dependencies=dependencies)
        return result

    async def prepare(self, session, *, project_id, resource_id, release_id, environment):
        store = configuration_for_session(session)
        if store is None:
            raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
        await store.lock_project(project_id)
        dependencies = await self.dependency_reader(session, project_id=project_id,
            bindings={str(resource_id): {"agent_id": str(resource_id), "release_id": str(release_id)}})
        return await store.activation_evidence(project_id=project_id, environment=environment,
            dependencies=dependencies)


class ConfigurationReleaseValidator:
    def __init__(self, uow, gate):
        self.uow, self.gate = uow, gate

    async def validate(self, release, environment):
        return await self.gate.prepare(self.uow.session, project_id=release.project_id,
            resource_id=release.agent_id, release_id=release.id, environment=environment)
