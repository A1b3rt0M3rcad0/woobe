from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.composition_resources import SESSION_FACTORY


def build_agent_uow() -> AgentUnitOfWork:
    return AgentUnitOfWork(SESSION_FACTORY)


def build_agent_read_uow() -> AgentUnitOfWork:
    """Short SQL read scope that always ends with rollback, never COMMIT."""

    return AgentUnitOfWork(SESSION_FACTORY, read_only=True)
