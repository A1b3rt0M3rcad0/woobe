from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentContractRepository
from modules.ai.service.use_cases import CreateContractUseCase
from modules.ai.presentation.controllers.create_contract_version_controller import CreateContractVersionController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_contract_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = CreateContractUseCase(repo)
    controller = CreateContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
