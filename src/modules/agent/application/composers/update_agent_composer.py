from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import UpdateAgentUseCase
from modules.agent.application.use_cases.legacy_runtime_status_adapter import (
    LegacyRuntimeStatusUpdateAdapter,
)
from modules.agent.infra.database.network_agent_usage_reader import (
    SQLAlchemyNetworkAgentUsageReader,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_agent_controller import UpdateAgentController
from shared.infra.transactional_handler import TransactionalHandler


def update_agent_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    agent_repo = uow.agents
    credential_repo = uow.provider_credentials
    provider_model_repo = uow.provider_models
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    network_usage_reader = SQLAlchemyNetworkAgentUsageReader(uow)
    update_use_case = UpdateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
        network_usage_reader,
    )
    use_case = LegacyRuntimeStatusUpdateAdapter(update_use_case, uow)
    controller = UpdateAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
