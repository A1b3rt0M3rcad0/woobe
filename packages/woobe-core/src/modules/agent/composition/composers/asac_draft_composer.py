from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.composition.composers.development_resources import build_development_resource_reader
from modules.agent.infra.database.asac_transactions import AgentASaCDraftStore
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def _uow_factory():
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    return uow


def build_agent_asac_drafts(*, artifacts):
    return AgentASaCDraftStore(uow_factory=_uow_factory,
        owner=build_development_resource_reader(), artifacts=artifacts, cursor_key=SETTINGS.secret_key)
