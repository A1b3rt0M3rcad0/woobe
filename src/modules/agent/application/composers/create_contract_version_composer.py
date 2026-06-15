from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentContractRepository
from modules.agent.application.use_cases import CreateContractUseCase
from modules.agent.presentation.controllers.create_contract_version_controller import CreateContractVersionController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_contract_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = CreateContractUseCase(repo)
    controller = CreateContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
