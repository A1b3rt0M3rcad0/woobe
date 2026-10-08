from modules.agent.application.use_cases.atomic_agent_update import AtomicAgentUpdateUseCase
from modules.agent.composition.composers.create_release_composer import build_complete_agent_draft
from modules.agent.infra.database.skill_repository import SQLAlchemySkillRepository
from modules.agent.application.use_cases import UpdateAgentUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.adapters.legacy_runtime_status_adapter import (
    LegacyRuntimeStatusUpdateAdapter,
)
from modules.agent.composition.factories.provider_dependency_reader_factory import build_agent_usage_reader
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_agent_controller import UpdateAgentController
from shared.infra.transactional_handler import TransactionalHandler


def update_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    network_usage_reader = build_agent_usage_reader(uow)
    update_use_case = UpdateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
        network_usage_reader,
        skill_repo=SQLAlchemySkillRepository(uow),
    )
    atomic = AtomicAgentUpdateUseCase(update_use_case, build_complete_agent_draft(uow), agent_repo)
    use_case = LegacyRuntimeStatusUpdateAdapter(atomic, uow)
    controller = UpdateAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
