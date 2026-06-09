from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentContractRepository
from modules.ai.service.use_cases import ListContractsUseCase
from modules.ai.presentation.controllers.list_contract_versions_controller import ListContractVersionsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_contract_versions_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = ListContractsUseCase(repo)
    controller = ListContractVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
