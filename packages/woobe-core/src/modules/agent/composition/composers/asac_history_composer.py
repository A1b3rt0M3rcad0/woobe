from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.composition.composers.development_resources import build_development_resource_reader
from modules.agent.infra.database.asac_history_reader import AgentHistoryReader
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def build_agent_history_reader():
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    uow.mark_read_only()
    return AgentHistoryReader(uow, build_development_resource_reader(), SETTINGS.secret_key)
