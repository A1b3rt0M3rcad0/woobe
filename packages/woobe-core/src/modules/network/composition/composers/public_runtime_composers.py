from modules.agent.entrypoint import NetworkAgentPromotionGateway
from modules.network.application.use_cases.execution_use_cases import (
    AcceptNetworkExecutionUseCase,
)
from modules.network.application.use_cases.public_runtime_use_cases import (
    SubmitPublicNetworkRunUseCase,
)
from modules.network.application.use_cases.session_use_cases import (
    CreateNetworkSessionUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.network.infra.database.execution_repository import (
    SQLAlchemyNetworkExecutionAcceptanceRepository,
)
from modules.network.infra.database.resource_repository import (
    SQLAlchemyNetworkResourceRepository,
)
from modules.network.infra.database.session_repository import (
    SQLAlchemyNetworkRuntimeEnvironmentRepository,
    SQLAlchemyNetworkSessionRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.public_runtime_controllers import (
    SubmitPublicNetworkRunController,
)
from shared.infra.transactional_handler import TransactionalHandler


def submit_public_network_run_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    network_repository = SQLAlchemyNetworkResourceRepository(uow)
    session_repository = SQLAlchemyNetworkSessionRepository(uow)
    environment_repository = SQLAlchemyNetworkRuntimeEnvironmentRepository(uow)
    acceptance_repository = SQLAlchemyNetworkExecutionAcceptanceRepository(uow)
    agent_gateway = NetworkAgentPromotionGateway(uow)

    create_session = CreateNetworkSessionUseCase(
        network_repository,
        session_repository,
        environment_repository,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    accept_execution = AcceptNetworkExecutionUseCase(
        acceptance_repository,
        agent_gateway,
        environment_repository,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    use_case = SubmitPublicNetworkRunUseCase(
        acceptance_repository,
        create_session,
        accept_execution,
    )
    controller = SubmitPublicNetworkRunController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = ["submit_public_network_run_composer"]
