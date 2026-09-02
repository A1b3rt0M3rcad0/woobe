from modules.network.application.use_cases.management_use_cases import (
    ActivateNetworkProductionUseCase,
    GetNetworkExecutionSnapshotUseCase,
    ListManagedNetworkVersionsUseCase,
    ListNetworkActivationsUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.management_repository import (
    SQLAlchemyNetworkManagementRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.management_controllers import (
    ActivateNetworkProductionController,
    GetNetworkExecutionSnapshotController,
    ListManagedNetworkVersionsController,
    ListNetworkActivationsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_managed_network_versions_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkManagementRepository(uow)
    use_case = ListManagedNetworkVersionsUseCase(repository)
    controller = ListManagedNetworkVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_network_activations_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkManagementRepository(uow)
    use_case = ListNetworkActivationsUseCase(repository)
    controller = ListNetworkActivationsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_network_execution_snapshot_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkManagementRepository(uow)
    use_case = GetNetworkExecutionSnapshotUseCase(repository)
    controller = GetNetworkExecutionSnapshotController(use_case)
    return TransactionalHandler(uow, controller.handle)


def activate_network_production_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkManagementRepository(uow)
    use_case = ActivateNetworkProductionUseCase(repository)
    controller = ActivateNetworkProductionController(use_case)
    return TransactionalHandler(uow, controller.handle)
