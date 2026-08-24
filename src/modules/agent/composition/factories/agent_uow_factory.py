from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.composition_resources import SESSION_FACTORY


def build_agent_uow() -> AgentUnitOfWork:
    """Create a fresh Agent UoW from the canonical process-scoped Session factory."""

    return AgentUnitOfWork(SESSION_FACTORY)
