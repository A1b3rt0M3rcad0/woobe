from modules.core.entrypoint import CoreProjectLookup
from modules.network.application.use_cases.compatibility_use_cases import (
    EnsureProjectNetworkUseCase,
    GetLegacyProjectNetworkUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.resource_repository import (
    SQLAlchemyNetworkResourceRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.compatibility_controllers import (
    EnsureProjectNetworkController,
    GetLegacyProjectNetworkController,
)
from shared.infra.transactional_handler import TransactionalHandler


def ensure_project_network_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkResourceRepository(uow)
    project_lookup = CoreProjectLookup()
    use_case = EnsureProjectNetworkUseCase(repository, project_lookup)
    controller = EnsureProjectNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_legacy_project_network_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkResourceRepository(uow)
    use_case = GetLegacyProjectNetworkUseCase(repository)
    controller = GetLegacyProjectNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)
