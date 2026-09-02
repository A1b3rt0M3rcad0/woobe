from modules.agent.entrypoint import NetworkAgentPromotionGateway
from modules.network.application.use_cases.execution_use_cases import (
    AcceptNetworkExecutionUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.network.infra.database.execution_repository import (
    SQLAlchemyNetworkExecutionAcceptanceRepository,
)
from modules.network.infra.database.session_repository import (
    SQLAlchemyNetworkRuntimeEnvironmentRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.execution_controllers import (
    AcceptNetworkExecutionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def accept_network_execution_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkExecutionAcceptanceRepository(uow)
    environment_repository = SQLAlchemyNetworkRuntimeEnvironmentRepository(uow)
    agent_gateway = NetworkAgentPromotionGateway(uow)
    use_case = AcceptNetworkExecutionUseCase(
        repository,
        agent_gateway,
        environment_repository,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    controller = AcceptNetworkExecutionController(use_case)
    return TransactionalHandler(uow, controller.handle)
