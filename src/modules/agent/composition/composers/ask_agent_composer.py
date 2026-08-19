from modules.agent.composition.runtime.ask_agent_runtime_factory import (
    build_ask_agent_handler,
)
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def ask_agent_composer(
    database: AgentDatabase,
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    handler = build_ask_agent_handler(database, settings, http_executor)
    return TransactionalHandler(uow, handler)
