from modules.core.infra.database.configuration_resolution import ConfigurationResolution


class ConfigurationRuntimeResolver:
    def __init__(self, session_factory, *, encryption_key, consumer_verifier):
        self.consumer_verifier = consumer_verifier
        self.session_factory, self.encryption_key = session_factory, encryption_key

    async def __call__(self, **identity):
        async with self.session_factory() as session:
            await self.consumer_verifier(session, project_id=identity["project_id"], consumer_kind=identity["consumer_kind"], consumer_id=identity["consumer_id"])
            return await ConfigurationResolution(session, encryption_key=self.encryption_key).resolve(**identity)
