from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentContractRepository
from modules.agent.application.use_cases.ai_use_cases import UpdateContractUseCase
from modules.agent.presentation.controllers.update_contract_version_controller import UpdateContractVersionController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def update_contract_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = UpdateContractUseCase(repo)
    controller = UpdateContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
