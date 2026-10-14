"""Host-owned Project barrier shared by Package Acceptance and source cutover."""
_factory = None


def configure_package_configuration_barrier(factory):
    global _factory
    _factory = factory


async def lock_configuration_project(session, project_id):
    if _factory is not None:
        await _factory(session).lock_project(project_id)
