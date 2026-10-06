from modules.agent.application.use_cases.commit_imported_mcp import (
    CommitImportedMcpUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.commit_imported_mcp_controller import (
    CommitImportedMcpController,
)
from shared.infra.transactional_handler import TransactionalHandler


def commit_imported_mcp_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    use_case = CommitImportedMcpUseCase(SQLAlchemyAgentToolRepository(uow))
    return TransactionalHandler(uow, CommitImportedMcpController(use_case).handle)
