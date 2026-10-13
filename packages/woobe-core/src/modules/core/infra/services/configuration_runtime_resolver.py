from modules.core.infra.database.configuration_resolution import ConfigurationResolution


class ConfigurationRuntimeResolver:
    def __init__(self, session_factory, *, encryption_key):
        self.session_factory, self.encryption_key = session_factory, encryption_key

    async def __call__(self, **identity):
        async with self.session_factory() as session:
            return await ConfigurationResolution(session, encryption_key=self.encryption_key).resolve(**identity)
