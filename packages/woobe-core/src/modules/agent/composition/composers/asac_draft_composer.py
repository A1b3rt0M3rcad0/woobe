from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.composition.composers.development_resources import build_development_resource_reader
from modules.agent.infra.database.asac_transactions import AgentASaCDraftStore
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def _uow_factory():
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    return uow


def build_agent_asac_drafts(*, artifacts):
    store = AgentASaCDraftStore(uow_factory=_uow_factory,
        owner=build_development_resource_reader(), artifacts=artifacts, cursor_key=SETTINGS.secret_key)
    from modules.agent.infra.database.asac_models import ASaCLeaseModel
    from modules.agent.infra.database.asac_transactions import AgentASaCLeaseStore
    store.leases=AgentASaCLeaseStore(drafts=store,leases=ASaCLeaseModel,
        maximum_ttl_seconds=SETTINGS.asac_lease_maximum_ttl_seconds,
        maximum_duration_seconds=SETTINGS.asac_lease_maximum_duration_seconds)
    return store


def build_agent_asac_candidates(*, artifacts, preparation):
    from modules.agent.infra.database.asac_models import ASaCCandidateModel
    from modules.agent.infra.database.asac_transactions import AgentASaCCandidateStore
    return AgentASaCCandidateStore(drafts=build_agent_asac_drafts(artifacts=artifacts),
        candidates=ASaCCandidateModel, preparation=preparation)


def build_agent_asac_evaluations(*, artifacts, preparation):
    from modules.agent.infra.database.asac_models import ASaCEvaluationModel
    from modules.agent.infra.execution.candidate_evaluation_runtime import AgentCandidateEvaluationRuntime
    from modules.agent.composition.factories.ask_agent_runtime_factory import build_ask_agent_handler
    from modules.agent.composition.resources import RUN_EVENT_JOURNAL
    from modules.agent.infra.database.asac_transactions import AgentASaCEvaluationStore
    runtime = AgentCandidateEvaluationRuntime(uow_factory=_uow_factory,
        handler=build_ask_agent_handler(SETTINGS), journal=RUN_EVENT_JOURNAL)
    return AgentASaCEvaluationStore(candidates=build_agent_asac_candidates(artifacts=artifacts, preparation=preparation),
        evaluations=ASaCEvaluationModel, runtime=runtime)


def build_agent_asac_publications(*, artifacts, preparation):
    from modules.agent.infra.database.asac_models import ASaCPublicationModel
    from modules.agent.infra.database.asac_publisher import AgentASaCPublisher
    from modules.agent.infra.database.asac_transactions import AgentASaCPublicationStore
    return AgentASaCPublicationStore(evaluations=build_agent_asac_evaluations(artifacts=artifacts,preparation=preparation),
        publications=ASaCPublicationModel,publisher=AgentASaCPublisher())


def build_agent_frozen_publication_gateway():
    from modules.agent.infra.database.asac_publisher import AgentASaCPublisher
    from modules.agent.infra.database.frozen_publication_gateway import AgentFrozenPublicationGateway
    from modules.agent.infra.database.frozen_snapshot_reader import AgentFrozenSnapshotReader
    from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
    return AgentFrozenPublicationGateway(drafts=build_agent_asac_drafts(artifacts=None),
        publisher=AgentASaCPublisher(), snapshots=AgentFrozenSnapshotReader(snapshot_builder=build_agent_execution_snapshot))


def build_agent_asac_leases(*, artifacts):
    return build_agent_asac_drafts(artifacts=artifacts).leases


def build_agent_asac_binding_guard(*, environment_reader):
    from modules.agent.infra.database.asac_binding_guard import AgentASaCBindingGuard
    return AgentASaCBindingGuard(environment_reader)


def build_agent_asac_deployments(*, artifacts, preparation, environment_reader):
    from modules.agent.infra.database.asac_models import ASaCDeploymentPlanModel, ASaCDeploymentModel, ASaCEnvironmentSelectionModel
    from modules.agent.infra.database.asac_transactions import AgentASaCDeploymentStore
    from modules.agent.infra.database.asac_environment_selector import AgentASaCEnvironmentSelector
    from modules.agent.infra.database.models import AgentOutboxEventModel
    return AgentASaCDeploymentStore(publications=build_agent_asac_publications(artifacts=artifacts,preparation=preparation),
        plans=ASaCDeploymentPlanModel,deployments=ASaCDeploymentModel,selections=ASaCEnvironmentSelectionModel,
        selector=AgentASaCEnvironmentSelector(),outbox=AgentOutboxEventModel,bindings=build_agent_asac_binding_guard(environment_reader=environment_reader))
