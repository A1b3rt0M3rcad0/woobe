from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.knowledge_release_validator import KnowledgeReleaseValidator
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeReleaseLifecycleUseCase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.promote_release_controller import PromoteReleaseController
from shared.infra.transactional_handler import TransactionalHandler


def promote_release_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    validator = KnowledgeReleaseValidator(uow.knowledge_versions, uow.vector_snapshots)
    use_case = KnowledgeSafeReleaseLifecycleUseCase(
        uow.releases,
        validator,
        uow.release_activations,
        activation_action="reactivate",
    )
    controller = PromoteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
