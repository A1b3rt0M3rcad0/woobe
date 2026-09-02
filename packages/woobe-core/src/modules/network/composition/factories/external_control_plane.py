from __future__ import annotations

from collections.abc import Callable
from typing import Any

from modules.network.application.interfaces.agent_availability import AgentAvailability
from modules.network.application.interfaces.agent_promotion import AgentPromotionGateway
from modules.network.application.interfaces.project_lookup import ProjectLookup
from modules.network.application.use_cases.compatibility_use_cases import (
    EnsureProjectNetworkUseCase,
    GetLegacyProjectNetworkUseCase,
)
from modules.network.application.use_cases.draft_use_cases import SaveNetworkDraftUseCase
from modules.network.application.use_cases.promotion_use_cases import (
    NetworkPromotionPlanner,
    PreviewNetworkPromotionUseCase,
    PromoteNetworkUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.network.infra.database.draft_repository import SQLAlchemyNetworkDraftRepository
from modules.network.infra.database.promotion_repository import (
    SQLAlchemyNetworkPromotionRepository,
)
from modules.network.infra.database.resource_repository import (
    SQLAlchemyNetworkResourceRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.compatibility_controllers import (
    EnsureProjectNetworkController,
    GetLegacyProjectNetworkController,
)
from modules.network.presentation.controllers.draft_controllers import SaveNetworkDraftController
from modules.network.presentation.controllers.promotion_controllers import (
    PreviewNetworkPromotionController,
    PromoteNetworkController,
)
from shared.infra.transactional_handler import TransactionalHandler


AgentPromotionGatewayFactory = Callable[[Any], AgentPromotionGateway]


def build_save_network_draft_handler(
    agent_availability: AgentAvailability,
) -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkDraftRepository(uow)
    use_case = SaveNetworkDraftUseCase(
        repository,
        agent_availability,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    controller = SaveNetworkDraftController(use_case)
    return TransactionalHandler(uow, controller.handle)


def _promotion_parts(
    agent_gateway_factory: AgentPromotionGatewayFactory,
):
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkPromotionRepository(uow)
    agent_gateway = agent_gateway_factory(uow)
    planner = NetworkPromotionPlanner(
        repository,
        agent_gateway,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    return uow, repository, agent_gateway, planner


def build_preview_network_promotion_handler(
    agent_gateway_factory: AgentPromotionGatewayFactory,
) -> TransactionalHandler:
    uow, _repository, _agent_gateway, planner = _promotion_parts(agent_gateway_factory)
    use_case = PreviewNetworkPromotionUseCase(planner)
    controller = PreviewNetworkPromotionController(use_case)
    return TransactionalHandler(uow, controller.handle)


def build_promote_network_handler(
    agent_gateway_factory: AgentPromotionGatewayFactory,
) -> TransactionalHandler:
    uow, repository, agent_gateway, planner = _promotion_parts(agent_gateway_factory)
    use_case = PromoteNetworkUseCase(planner, repository, agent_gateway)
    controller = PromoteNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)


def build_ensure_project_network_handler(
    project_lookup: ProjectLookup,
) -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkResourceRepository(uow)
    use_case = EnsureProjectNetworkUseCase(repository, project_lookup)
    controller = EnsureProjectNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)


def build_get_legacy_project_network_handler() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    uow.mark_read_only()
    repository = SQLAlchemyNetworkResourceRepository(uow)
    use_case = GetLegacyProjectNetworkUseCase(repository)
    controller = GetLegacyProjectNetworkController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "AgentPromotionGatewayFactory",
    "build_ensure_project_network_handler",
    "build_get_legacy_project_network_handler",
    "build_preview_network_promotion_handler",
    "build_promote_network_handler",
    "build_save_network_draft_handler",
]
