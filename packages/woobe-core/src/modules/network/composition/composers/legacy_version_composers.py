from modules.network.application.use_cases.management_use_cases import (
    ListManagedNetworkVersionsUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.management_repository import (
    SQLAlchemyNetworkManagementRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.legacy_version_controllers import (
    ListLegacyNetworkVersionsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_network_versions_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkManagementRepository(uow)
    use_case = ListManagedNetworkVersionsUseCase(repository)
    controller = ListLegacyNetworkVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
