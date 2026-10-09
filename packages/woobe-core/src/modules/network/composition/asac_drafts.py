from modules.network.infra.database.asac_models import ASaCDraftModel, ASaCRevisionModel, ASaCOperationModel, ASaCResourceModel
from modules.network.infra.services.development_resource_reader import DevelopmentNetworkReader
from shared.composition_resources import SESSION_FACTORY, SETTINGS
from shared.infra.asac_draft_store import ASaCDraftStore


def build_network_asac_drafts(*, artifacts):
    store = ASaCDraftStore(transactions=SESSION_FACTORY, kind="Network",
        owner=DevelopmentNetworkReader(), drafts=ASaCDraftModel,
        revisions=ASaCRevisionModel, operations=ASaCOperationModel,
        identities=ASaCResourceModel, artifacts=artifacts, cursor_key=SETTINGS.secret_key)
    from modules.network.infra.database.asac_models import ASaCLeaseModel
    from shared.infra.asac_lease_store import ASaCLeaseStore
    store.leases=ASaCLeaseStore(drafts=store,leases=ASaCLeaseModel,
        maximum_ttl_seconds=SETTINGS.asac_lease_maximum_ttl_seconds,
        maximum_duration_seconds=SETTINGS.asac_lease_maximum_duration_seconds)
    return store


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


def build_network_asac_publications(*, artifacts, preparation):
    from modules.agent.entrypoint import build_agent_frozen_publication_gateway
    from modules.network.infra.database.asac_models import ASaCPublicationModel
    from modules.network.infra.services.asac_native_publisher import NetworkASaCNativePublisher
    from modules.network.infra.services.asac_publication_store import NetworkASaCPublicationStore
    return NetworkASaCPublicationStore(evaluations=build_network_asac_evaluations(artifacts=artifacts, preparation=preparation),
        publications=ASaCPublicationModel, publisher=NetworkASaCNativePublisher(),
        constituents=build_agent_frozen_publication_gateway())


def build_network_asac_leases(*, artifacts):
    return build_network_asac_drafts(artifacts=artifacts).leases


def build_network_asac_deployments(*, artifacts, preparation, environment_reader):
    from modules.agent.entrypoint import build_agent_asac_binding_guard
    from modules.network.infra.database.asac_models import ASaCDeploymentPlanModel, ASaCDeploymentModel, ASaCEnvironmentSelectionModel
    from modules.network.infra.database.models import NetworkOutboxEventModel
    from modules.network.infra.services.asac_environment_selector import NetworkASaCEnvironmentSelector
    from shared.infra.asac_deployment_store import ASaCDeploymentStore
    return ASaCDeploymentStore(publications=build_network_asac_publications(artifacts=artifacts,preparation=preparation),
        plans=ASaCDeploymentPlanModel,deployments=ASaCDeploymentModel,selections=ASaCEnvironmentSelectionModel,
        selector=NetworkASaCEnvironmentSelector(),outbox=NetworkOutboxEventModel,bindings=build_agent_asac_binding_guard(environment_reader=environment_reader))
