from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentContractRepository
from modules.agent.application.use_cases import UpdateContractUseCase
from modules.agent.presentation.controllers.update_contract_version_controller import UpdateContractVersionController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def update_contract_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = UpdateContractUseCase(repo)
    controller = UpdateContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
