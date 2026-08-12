from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.knowledge_release_validator import KnowledgeReleaseValidator
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeRollbackReleaseUseCase
from modules.agent.presentation.controllers.rollback_release_controller import RollbackReleaseController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def rollback_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    validator = KnowledgeReleaseValidator(uow.knowledge_versions, uow.vector_snapshots)
    use_case = KnowledgeSafeRollbackReleaseUseCase(
        uow.releases,
        validator,
        uow.release_activations,
        activation_action="rollback",
    )
    controller = RollbackReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
