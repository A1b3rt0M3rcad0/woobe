from modules.core.entrypoint import CoreProjectLookup
from modules.network.application.use_cases.resource_use_cases import (
    CreateProjectNetworkUseCase,
    GetProjectNetworkUseCase,
    ListProjectNetworksUseCase,
    UpdateProjectNetworkUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.resource_repository import (
    SQLAlchemyNetworkResourceRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.resource_controllers import (
    CreateProjectNetworkController,
    GetProjectNetworkController,
    ListProjectNetworksController,
    UpdateProjectNetworkController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_project_networks_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkResourceRepository(uow)
    project_lookup = CoreProjectLookup()
    use_case = ListProjectNetworksUseCase(repository, project_lookup)
    controller = ListProjectNetworksController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_project_network_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkResourceRepository(uow)
    project_lookup = CoreProjectLookup()
    use_case = CreateProjectNetworkUseCase(repository, project_lookup)
    controller = CreateProjectNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_project_network_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkResourceRepository(uow)
    use_case = GetProjectNetworkUseCase(repository)
    controller = GetProjectNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_project_network_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkResourceRepository(uow)
    use_case = UpdateProjectNetworkUseCase(repository)
    controller = UpdateProjectNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)
