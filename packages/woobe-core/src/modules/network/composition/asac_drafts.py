from modules.network.infra.database.asac_models import ASaCDraftModel, ASaCRevisionModel, ASaCOperationModel, ASaCResourceModel
from modules.network.infra.services.development_resource_reader import DevelopmentNetworkReader
from shared.composition_resources import SESSION_FACTORY, SETTINGS
from shared.infra.asac_draft_store import ASaCDraftStore


def build_network_asac_drafts(*, artifacts):
    return ASaCDraftStore(transactions=SESSION_FACTORY, kind="Network",
        owner=DevelopmentNetworkReader(), drafts=ASaCDraftModel,
        revisions=ASaCRevisionModel, operations=ASaCOperationModel,
        identities=ASaCResourceModel, artifacts=artifacts, cursor_key=SETTINGS.secret_key)


def build_network_asac_candidates(*, artifacts, preparation):
    from modules.network.infra.database.asac_models import ASaCCandidateModel
    from shared.infra.asac_candidate_store import ASaCCandidateStore
    return ASaCCandidateStore(drafts=build_network_asac_drafts(artifacts=artifacts),
        candidates=ASaCCandidateModel, preparation=preparation)


def build_network_asac_evaluations(*, artifacts, preparation):
    from modules.network.infra.database.asac_models import ASaCEvaluationModel
    from modules.network.infra.services.candidate_evaluation_runtime import NetworkCandidateEvaluationRuntime
    from modules.network.composition.services import build_network_service
    from shared.composition_resources import RUN_EVENT_JOURNAL
    from shared.infra.asac_evaluation_store import ASaCEvaluationStore
    runtime = NetworkCandidateEvaluationRuntime(sessions=SESSION_FACTORY,
        service=build_network_service(), journal=RUN_EVENT_JOURNAL)
    return ASaCEvaluationStore(candidates=build_network_asac_candidates(artifacts=artifacts, preparation=preparation),
        evaluations=ASaCEvaluationModel, runtime=runtime)


def build_network_candidate_admission_reader():
    from modules.network.infra.services.candidate_evaluation_runtime import NetworkCandidateRuntimeAdmissionReader
    return NetworkCandidateRuntimeAdmissionReader(SESSION_FACTORY)
