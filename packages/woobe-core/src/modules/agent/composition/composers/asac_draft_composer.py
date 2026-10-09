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
