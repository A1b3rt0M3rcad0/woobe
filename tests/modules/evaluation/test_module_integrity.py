from __future__ import annotations

import importlib

from modules.evaluation.application.catalog_service import EvaluationCatalogService
from modules.evaluation.application.completed_service import (
    CompletedEvaluationApplicationService,
)
from modules.evaluation.application.contract_aware_authoring import (
    ContractAwareEvaluationSuiteAuthoringService,
)
from modules.evaluation.application.diagnostic_authoring import (
    DiagnosticEvaluationSuiteAuthoringService,
)
from modules.evaluation.application.durable_authoring import (
    DurableEvaluationSuiteAuthoringService,
)
from modules.evaluation.application.enriched_service import (
    EnrichedEvaluationApplicationService,
)
from modules.evaluation.application.evidence_service import (
    EvidenceRichEvaluationApplicationService,
)
from modules.evaluation.application.experience_service import (
    EvaluationExperienceService,
)
from modules.evaluation.application.hardened_service import (
    HardenedEvaluationApplicationService,
)
from modules.evaluation.application.human_decision_service import (
    HumanDecisionEvaluationApplicationService,
)
from modules.evaluation.application.revision_aware_experience import (
    RevisionAwareEvaluationExperienceService,
)
from modules.evaluation.application.revision_comparison_service import (
    RevisionComparisonCatalogService,
)
from modules.evaluation.application.resumable_authoring import (
    ResumableEvaluationSuiteAuthoringService,
)
from modules.evaluation.application.runtime_gateway import (
    EvaluationNetworkRuntimeGateway,
)
from modules.evaluation.application.suite_authoring import (
    EvaluationSuiteAuthoringService,
)
from modules.evaluation.infra.adaptive_judge import AdaptiveEvaluatorModelGateway
from modules.evaluation.infra.database.catalog_models import (
    EvaluationComparisonDecisionModel,
    EvaluationComparisonModel,
    EvaluationModel,
)
from modules.evaluation.infra.database.decision_models import (
    EvaluationTargetDecisionModel,
)
from modules.evaluation.infra.database.evidence_revision_models import (
    EvaluationEvidenceRevisionModel,
)
from modules.evaluation.infra.workers.authoring_worker import EvaluationAuthoringWorker
from modules.evaluation.infra.workers.concurrent_worker import (
    ConcurrentOutcomeAwareEvaluationRunProcessor,
    ConcurrentOutcomeAwareEvaluationRunWorker,
)
from modules.evaluation.infra.workers.governed_worker import (
    GovernedEvaluationRunProcessor,
    GovernedEvaluationRunWorker,
)
from modules.evaluation.infra.workers.integrity_worker import (
    IntegrityEvaluationRunProcessor,
    IntegrityEvaluationRunWorker,
)
from modules.evaluation.infra.workers.outcome_worker import (
    OutcomeAwareEvaluationRunProcessor,
    OutcomeAwareEvaluationRunWorker,
)
from modules.evaluation.infra.workers.registry import (
    EvaluationWorkerRegistry,
    register_evaluation_workers,
)
from modules.evaluation.infra.workers.resumable_authoring_worker import (
    ResumableEvaluationAuthoringWorker,
)
from modules.evaluation.infra.workers.run_worker import (
    ResumableEvaluationRunProcessor,
    ResumableEvaluationRunWorker,
)
from modules.evaluation.infra.workers.slot_ready_authoring_worker import (
    SlotReadyEvaluationAuthoringWorker,
)
from modules.network.application.agent_invoker import ProjectRAIAgentInvoker
from modules.network.infra.runtime import (
    ProjectRAIAgentInvoker as CanonicalProjectRAIAgentInvoker,
)
from shared.workers.contracts import WorkerProtocol
from shared.workers.discovery import discover_module_entries


def test_network_agent_invoker_compatibility_import_is_canonical() -> None:
    assert ProjectRAIAgentInvoker is CanonicalProjectRAIAgentInvoker


def test_evaluation_module_imports_are_resolvable() -> None:
    assert HardenedEvaluationApplicationService is not None
    assert EnrichedEvaluationApplicationService is not None
    assert CompletedEvaluationApplicationService is not None
    assert HumanDecisionEvaluationApplicationService is not None
    assert EvaluationExperienceService is not None
    assert RevisionAwareEvaluationExperienceService is not None
    assert EvidenceRichEvaluationApplicationService is not None
    assert EvaluationCatalogService is not None
    assert RevisionComparisonCatalogService is not None
    assert EvaluationTargetDecisionModel is not None
    assert EvaluationModel is not None
    assert EvaluationComparisonModel is not None
    assert EvaluationComparisonDecisionModel is not None
    assert EvaluationEvidenceRevisionModel is not None
    assert EvaluationSuiteAuthoringService is not None
    assert DurableEvaluationSuiteAuthoringService is not None
    assert DiagnosticEvaluationSuiteAuthoringService is not None
    assert ContractAwareEvaluationSuiteAuthoringService is not None
    assert ResumableEvaluationSuiteAuthoringService is not None
    assert EvaluationNetworkRuntimeGateway is not None
    assert AdaptiveEvaluatorModelGateway is not None
    assert ResumableEvaluationRunProcessor is not None
    assert ResumableEvaluationRunWorker is not None
    assert OutcomeAwareEvaluationRunProcessor is not None
    assert OutcomeAwareEvaluationRunWorker is not None
    assert ConcurrentOutcomeAwareEvaluationRunProcessor is not None
    assert ConcurrentOutcomeAwareEvaluationRunWorker is not None
    assert GovernedEvaluationRunProcessor is not None
    assert GovernedEvaluationRunWorker is not None
    assert IntegrityEvaluationRunProcessor is not None
    assert IntegrityEvaluationRunWorker is not None
    assert EvaluationAuthoringWorker is not None
    assert ResumableEvaluationAuthoringWorker is not None
    assert SlotReadyEvaluationAuthoringWorker is not None
    assert EvaluationWorkerRegistry is not None
    assert register_evaluation_workers is not None


def test_evaluation_authoring_modules_import_cleanly() -> None:
    module_names = [
        "modules.evaluation.application.catalog_service",
        "modules.evaluation.application.compatible_resumable_authoring",
        "modules.evaluation.application.completed_service",
        "modules.evaluation.application.context_pack",
        "modules.evaluation.application.contract_aware_authoring",
        "modules.evaluation.application.diagnostic_authoring",
        "modules.evaluation.application.durable_authoring",
        "modules.evaluation.application.enriched_service",
        "modules.evaluation.application.evaluation_protocol",
        "modules.evaluation.application.evidence_revision_snapshot",
        "modules.evaluation.application.evidence_service",
        "modules.evaluation.application.experience_service",
        "modules.evaluation.application.failure_taxonomy",
        "modules.evaluation.application.human_decision_service",
        "modules.evaluation.application.immutable_catalog_service",
        "modules.evaluation.application.metering",
        "modules.evaluation.application.operational_service",
        "modules.evaluation.application.outcome_scoring",
        "modules.evaluation.application.revision_aware_experience",
        "modules.evaluation.application.revision_comparison_service",
        "modules.evaluation.application.resumable_authoring",
        "modules.evaluation.application.secure_authoring",
        "modules.evaluation.application.suite_authoring",
        "modules.evaluation.application.token_budget",
        "modules.evaluation.application.tool_catalog",
        "modules.evaluation.application.tool_reference_repair",
        "modules.evaluation.domain.authoring_contract",
        "modules.evaluation.domain.contracts",
        "modules.evaluation.infra.adaptive_judge",
        "modules.evaluation.infra.budgeted_judge",
        "modules.evaluation.infra.database.authoring_models",
        "modules.evaluation.infra.database.catalog_models",
        "modules.evaluation.infra.database.decision_models",
        "modules.evaluation.infra.database.evidence_revision_models",
        "modules.evaluation.infra.generator",
        "modules.evaluation.infra.workers.authoring_worker",
        "modules.evaluation.infra.workers.concurrent_worker",
        "modules.evaluation.infra.workers.governed_worker",
        "modules.evaluation.infra.workers.integrity_worker",
        "modules.evaluation.infra.workers.outcome_worker",
        "modules.evaluation.infra.workers.resumable_authoring_worker",
        "modules.evaluation.infra.workers.slot_ready_authoring_worker",
        "modules.evaluation.presentation.authoring_routes",
        "modules.evaluation.presentation.catalog_routes",
        "modules.evaluation.presentation.comparison_preview_routes",
        "modules.evaluation.presentation.decision_routes",
        "modules.evaluation.presentation.evidence_routes",
        "modules.evaluation.presentation.experience_routes",
        "modules.evaluation.presentation.routes",
    ]
    for module_name in module_names:
        assert importlib.import_module(module_name) is not None


def test_evaluation_worker_registry_is_discoverable() -> None:
    entries = discover_module_entries()
    evaluation = next(item for item in entries if item.module_name == "evaluation")

    assert evaluation.registry_class is EvaluationWorkerRegistry
    assert evaluation.register_func is register_evaluation_workers


def test_evaluation_workers_implement_worker_contract() -> None:
    assert isinstance(
        IntegrityEvaluationRunWorker.__new__(IntegrityEvaluationRunWorker),
        WorkerProtocol,
    )
    assert isinstance(
        SlotReadyEvaluationAuthoringWorker.__new__(
            SlotReadyEvaluationAuthoringWorker
        ),
        WorkerProtocol,
    )
