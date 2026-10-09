from modules.agent.application.use_cases.create_candidate_snapshot import CreateCandidateSnapshot
from modules.agent.application.use_cases.knowledge_release_validator import KnowledgeReleaseValidator
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeCreateReleaseUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels, SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository, SQLAlchemyKnowledgeVersionRepository
from modules.agent.infra.database.project_environment_reader import SQLAlchemyProjectEnvironmentReader
from modules.agent.infra.database.skill_repository import SQLAlchemySkillRepository
from modules.agent.infra.database.vector_snapshot_repositories import SQLAlchemyVectorSnapshotRepository
from modules.agent.presentation.controllers.candidate_snapshot_controller import CandidateSnapshotController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.candidate_lifecycle import AgentCandidateLifecycleHandler
from modules.agent.composition.composers.development_resources import build_development_resource_reader


def create_candidate_snapshot_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    releases = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    preparation = KnowledgeSafeCreateReleaseUseCase(releases,
        KnowledgeReleaseValidator(SQLAlchemyKnowledgeVersionRepository(uow), SQLAlchemyVectorSnapshotRepository(uow)),
        SQLAlchemyAgentToolRepository(uow), SQLAlchemySkillRepository(uow),
        project_environment_reader=SQLAlchemyProjectEnvironmentReader(uow))
    use_case = CreateCandidateSnapshot(agents=SQLAlchemyAgentRepositoryWithProviderModels(uow),
        releases=releases, preparation=preparation)
    controller = CandidateSnapshotController(use_case)
    return TransactionalHandler(uow, controller.handle)


def agent_candidate_lifecycle_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    handler = AgentCandidateLifecycleHandler(uow, build_development_resource_reader(),
        SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow))
    return TransactionalHandler(uow, handler.handle)

from modules.agent.application.interfaces.candidate_execution import CandidateExecutionGrant, candidate_execution
