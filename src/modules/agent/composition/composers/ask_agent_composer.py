from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
)
from modules.agent.composition.resources import AGENT_DATABASE, DATABASE_ENGINE, SETTINGS
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def ask_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    handler = build_ask_agent_handler(AGENT_DATABASE, SETTINGS)
    return TransactionalHandler(uow, handler)
