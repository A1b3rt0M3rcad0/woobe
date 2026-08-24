from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def build_agent_uow() -> AgentUnitOfWork:
    """Create a fresh Agent UoW from the canonical process-scoped engine."""

    return AgentUnitOfWork(DATABASE_ENGINE)
