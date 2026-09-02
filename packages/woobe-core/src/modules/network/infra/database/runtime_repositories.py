from dataclasses import dataclass

from modules.network.application.interfaces.project_access_repository import (
    NetworkProjectAccessRepository,
)
from modules.network.application.interfaces.run_observation_repository import (
    NetworkRunObservationRepository,
)
from modules.network.infra.database.project_access_repository import (
    SQLAlchemyNetworkProjectAccessRepository,
)
from modules.network.infra.database.run_observation_repository import (
    SQLAlchemyNetworkRunObservationRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


@dataclass(frozen=True)
class NetworkRuntimeRepositories:
    runs: NetworkRunObservationRepository
    project_access: NetworkProjectAccessRepository


def build_network_runtime_repositories(
    uow: NetworkUnitOfWork,
) -> NetworkRuntimeRepositories:
    return NetworkRuntimeRepositories(
        runs=SQLAlchemyNetworkRunObservationRepository(uow),
        project_access=SQLAlchemyNetworkProjectAccessRepository(uow),
    )
