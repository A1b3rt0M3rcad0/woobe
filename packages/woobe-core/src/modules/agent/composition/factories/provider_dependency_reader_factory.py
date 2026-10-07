from modules.agent.infra.database.provider_dependency_reader import (
    SQLProviderDependencyReader,
)

_network_consumers = None
_surface_consumers = None


def configure_provider_dependency_readers(*, network_consumers, surface_consumers):
    global _network_consumers, _surface_consumers
    _network_consumers, _surface_consumers = network_consumers, surface_consumers


def build_provider_dependency_reader(uow):
    return SQLProviderDependencyReader(
        uow,
        network_consumers=_network_consumers,
        surface_consumers=_surface_consumers,
    )
