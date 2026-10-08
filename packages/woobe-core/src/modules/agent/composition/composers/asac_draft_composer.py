from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.composition.composers.development_resources import build_development_resource_reader
from modules.agent.infra.database.asac_models import ASaCDraftModel, ASaCRevisionModel, ASaCOperationModel, ASaCResourceModel
from modules.agent.infra.database.asac_transactions import AgentASaCTransactions
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.asac_draft_store import ASaCDraftStore


def _uow_factory():
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    return uow


def build_agent_asac_drafts():
    from modules.package.entrypoint import build_snapshot_artifacts
    return ASaCDraftStore(transactions=AgentASaCTransactions(_uow_factory), kind="Agent",
        owner=build_development_resource_reader(), drafts=ASaCDraftModel,
        revisions=ASaCRevisionModel, operations=ASaCOperationModel,
        identities=ASaCResourceModel, artifacts=build_snapshot_artifacts())
