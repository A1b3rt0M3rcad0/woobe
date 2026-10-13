"""Host-injected closure reader, resolved by the central configuration owner."""

class ConfigurationAcceptance:
    def __init__(self, store_factory, dependency_reader):
        self.store_factory, self.dependency_reader = store_factory, dependency_reader

    async def lock(self, session, *, project_id):
        await self.store_factory(session).lock_project(project_id)

    async def __call__(self, session, *, project_id, run_id, environment, bindings):
        store = self.store_factory(session)
        await store.lock_project(project_id)
        dependencies = await self.dependency_reader(session, project_id=project_id, bindings=bindings)
        if not dependencies:
            return []
        return await store.acquire(project_id=project_id, run_id=run_id,
            environment=environment, dependencies=dependencies)

    async def prepare(self, session, *, project_id, environment, bindings):
        store = self.store_factory(session)
        await store.lock_project(project_id)
        dependencies = await self.dependency_reader(session, project_id=project_id, bindings=bindings)
        return await store.activation_evidence(project_id=project_id,
            environment=environment, dependencies=dependencies)

    async def status(self, session, *, project_id, environment, bindings):
        store = self.store_factory(session)
        dependencies = await self.dependency_reader(session, project_id=project_id, bindings=bindings)
        result, _pins = await store.inspect(project_id=project_id, environment=environment, dependencies=dependencies)
        return result
