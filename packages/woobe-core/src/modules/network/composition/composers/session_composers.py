from modules.network.application.use_cases.session_use_cases import (
    CreateNetworkSessionUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.network.infra.database.resource_repository import (
    SQLAlchemyNetworkResourceRepository,
)
from modules.network.infra.database.session_repository import (
    SQLAlchemyNetworkRuntimeEnvironmentRepository,
    SQLAlchemyNetworkSessionRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.session_controllers import (
    CreateNetworkSessionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_network_session_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    network_repository = SQLAlchemyNetworkResourceRepository(uow)
    session_repository = SQLAlchemyNetworkSessionRepository(uow)
    environment_repository = SQLAlchemyNetworkRuntimeEnvironmentRepository(uow)
    use_case = CreateNetworkSessionUseCase(
        network_repository,
        session_repository,
        environment_repository,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    controller = CreateNetworkSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)
