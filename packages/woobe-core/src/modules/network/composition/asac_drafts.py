from modules.network.infra.database.asac_models import ASaCDraftModel, ASaCRevisionModel, ASaCOperationModel, ASaCResourceModel
from modules.network.infra.services.development_resource_reader import DevelopmentNetworkReader
from shared.composition_resources import SESSION_FACTORY
from shared.infra.asac_draft_store import ASaCDraftStore


def build_network_asac_drafts(*, artifacts):
    return ASaCDraftStore(transactions=SESSION_FACTORY, kind="Network",
        owner=DevelopmentNetworkReader(), drafts=ASaCDraftModel,
        revisions=ASaCRevisionModel, operations=ASaCOperationModel,
        identities=ASaCResourceModel, artifacts=artifacts)
