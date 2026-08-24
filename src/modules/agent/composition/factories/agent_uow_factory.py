from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.composition_resources import DATABASE_ENGINE


def build_agent_uow() -> AgentUnitOfWork:
    return AgentUnitOfWork(DATABASE_ENGINE)


def build_agent_read_uow() -> AgentUnitOfWork:
    """Short SQL read scope that always ends with rollback, never COMMIT."""

    return AgentUnitOfWork(DATABASE_ENGINE).mark_read_only()
