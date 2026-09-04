from modules.agent.application.use_cases import CreateAgentUseCase
from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_agent_controller import CreateAgentController
from shared.infra.transactional_handler import TransactionalHandler


def create_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
        default_context_manager=SETTINGS.default_context_manager,
    )
    controller = CreateAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
