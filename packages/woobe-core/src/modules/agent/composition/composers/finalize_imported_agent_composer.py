from modules.agent.application.use_cases.ai_agent_cases import UpdateAgentUseCase
from modules.agent.application.use_cases.finalize_imported_agent import (
    FinalizeImportedAgentUseCase,
)
from modules.agent.application.use_cases.knowledge_release_validator import (
    KnowledgeReleaseValidator,
)
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import (
    KnowledgeSafeCreateReleaseUseCase,
)
from modules.agent.application.use_cases.session_mode_compatible_release import (
    SessionModeCompatibleCreateReleaseUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.network_agent_usage_reader import (
    SQLAlchemyNetworkAgentUsageReader,
)
from modules.agent.infra.database.project_environment_reader import (
    SQLAlchemyProjectEnvironmentReader,
)
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAgentToolRepository,
    SQLAlchemyKnowledgeVersionRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.skill_repository import SQLAlchemySkillRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_repositories import (
    SQLAlchemyVectorSnapshotRepository,
)
from modules.agent.presentation.controllers.create_release_controller import (
    CreateReleaseController,
)
from shared.infra.transactional_handler import TransactionalHandler


def finalize_imported_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    agents = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    releases = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    knowledge = SQLAlchemyKnowledgeVersionRepository(uow)
    vectors = SQLAlchemyVectorSnapshotRepository(uow)
    tools = SQLAlchemyAgentToolRepository(uow)
    skills = SQLAlchemySkillRepository(uow)
    environment = SQLAlchemyProjectEnvironmentReader(uow)
    credentials = SQLAlchemyProviderCredentialRepository(uow)
    models = SQLAlchemyProviderModelRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    usage = SQLAlchemyNetworkAgentUsageReader(uow)
    validator = KnowledgeReleaseValidator(knowledge, vectors)
    save_release = KnowledgeSafeCreateReleaseUseCase(
        releases, validator, tools, skills, project_environment_reader=environment
    )
    save_draft = SessionModeCompatibleCreateReleaseUseCase(save_release, agents)
    update = UpdateAgentUseCase(
        agents, credentials, outbox, models, usage, skill_repo=skills
    )
    use_case = FinalizeImportedAgentUseCase(save_draft, update, agents)
    controller = CreateReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
