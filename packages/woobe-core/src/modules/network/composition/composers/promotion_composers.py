from modules.agent.entrypoint import NetworkAgentPromotionGateway
from modules.network.application.use_cases.promotion_use_cases import (
    NetworkPromotionPlanner,
    PreviewNetworkPromotionUseCase,
    PromoteNetworkUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.network.infra.database.promotion_repository import (
    SQLAlchemyNetworkPromotionRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.promotion_controllers import (
    PreviewNetworkPromotionController,
    PromoteNetworkController,
)
from shared.infra.transactional_handler import TransactionalHandler


def preview_network_promotion_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkPromotionRepository(uow)
    agent_gateway = NetworkAgentPromotionGateway(uow)
    planner = NetworkPromotionPlanner(
        repository,
        agent_gateway,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    use_case = PreviewNetworkPromotionUseCase(planner)
    controller = PreviewNetworkPromotionController(use_case)
    return TransactionalHandler(uow, controller.handle)


def promote_network_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkPromotionRepository(uow)
    agent_gateway = NetworkAgentPromotionGateway(uow)
    planner = NetworkPromotionPlanner(
        repository,
        agent_gateway,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    use_case = PromoteNetworkUseCase(planner, repository, agent_gateway)
    controller = PromoteNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)
