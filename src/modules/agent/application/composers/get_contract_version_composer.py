from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentContractRepository
from modules.agent.application.use_cases import GetContractUseCase
from modules.agent.presentation.controllers.get_contract_version_controller import GetContractVersionController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def get_contract_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = GetContractUseCase(repo)
    controller = GetContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
