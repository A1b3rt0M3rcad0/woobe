"""Host composition of owner-scoped dependency readers."""
from modules.agent.entrypoint import collect_configuration_dependencies, read_configuration_target
from modules.core.entrypoint import configure_configuration_target_reader
from modules.network.entrypoint import read_configuration_bindings


async def target_reader(session, *, project_id, target_kind, target_id, environment, version_id=None):
    if target_kind == "network":
        target = await read_configuration_bindings(session, project_id=project_id,
            target_id=target_id, environment=environment, version_id=version_id)
        result = await collect_configuration_dependencies(session, project_id=project_id,
            bindings=target["bindings"], include_notices=True)
        result["selection"] = target["selection"]
        return result
    return await read_configuration_target(session, project_id=project_id, target_kind=target_kind,
        target_id=target_id, environment=environment, version_id=version_id)


def configure_target_readiness():
    from modules.package.entrypoint import configure_package_configuration_barrier
    from modules.core.entrypoint import build_project_configuration_runtime
    configure_package_configuration_barrier(build_project_configuration_runtime)
    configure_configuration_target_reader(target_reader)
    from modules.agent.entrypoint import configuration_binding
    from modules.core.entrypoint import configure_configuration_binding_adapter
    configure_configuration_binding_adapter(configuration_binding)
    from modules.agent.entrypoint import inventory_provider_configuration, migrate_provider_configuration
    from modules.core.entrypoint import configure_configuration_migration_adapter
    configure_configuration_migration_adapter(inventory=inventory_provider_configuration, cutover=migrate_provider_configuration,
        assert_quiescent=assert_configuration_quiescent)


async def assert_configuration_quiescent(session, *, project_id):
    from modules.agent.entrypoint import assert_agent_configuration_quiescent
    from modules.network.entrypoint import assert_network_configuration_quiescent
    from modules.package.entrypoint import assert_package_configuration_quiescent
    await assert_agent_configuration_quiescent(session, project_id=project_id)
    await assert_network_configuration_quiescent(session, project_id=project_id)
    await assert_package_configuration_quiescent(session, project_id=project_id)
