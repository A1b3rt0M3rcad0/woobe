from modules.agent.composition.resources import SESSION_FACTORY, SETTINGS
from modules.agent.composition.composers.development_resources import build_development_resource_reader
from modules.agent.infra.database.asac_history_reader import AgentHistoryReader


def build_agent_history_reader():
    return AgentHistoryReader(SESSION_FACTORY, build_development_resource_reader(), SETTINGS.secret_key)
