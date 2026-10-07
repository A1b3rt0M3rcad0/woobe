from modules.network.composition.resources import SESSION_FACTORY
from modules.network.infra.database.dependency_impact_reader import (
    NetworkDependencyImpactReader,
)


def build_network_dependency_impact_reader():
    return NetworkDependencyImpactReader(SESSION_FACTORY)
