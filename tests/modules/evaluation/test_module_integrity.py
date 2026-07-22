from __future__ import annotations

import importlib

from modules.evaluation.application.completed_service import (
    CompletedEvaluationApplicationService,
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
from modules.evaluation.application.experience_service import (
    EvaluationExperienceService,
)
from modules.evaluation.application.hardened_service import (
    HardenedEvaluationApplicationService,
)
from modules.evaluation.application.runtime_gateway import (
    EvaluationNetworkRuntimeGateway,
)
from modules.evaluation.application.suite_authoring import (
    EvaluationSuiteAuthoringService,
)
from modules.evaluation.infra.adaptive_judge import AdaptiveEvaluatorModelGateway
from modules.evaluation.infra.workers.authoring_worker import EvaluationAuthoringWorker
from modules.evaluation.infra.workers.concurrent_worker import (
    ConcurrentOutcomeAwareEvaluationRunProcessor,
    ConcurrentOutcomeAwareEvaluationRunWorker,
)
from modules.evaluation.infra.workers.outcome_worker import (
    OutcomeAwareEvaluationRunProcessor,
    OutcomeAwareEvaluationRunWorker,
)
from modules.evaluation.infra.workers.registry import (
    EvaluationWorkerRegistry,
    register_evaluation_workers,
)
from modules.evaluation.infra.workers.run_worker import (
    ResumableEvaluationRunProcessor,
    ResumableEvaluationRunWorker,
)
from modules.evaluation.infra.workers.variant_worker import (
    VariantAwareConcurrentEvaluationRunProcessor,
    VariantAwareConcurrentEvaluationRunWorker,
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
    assert EvaluationExperienceService is not None
    assert EvaluationSuiteAuthoringService is not None
    assert DurableEvaluationSuiteAuthoringService is not None
    assert DiagnosticEvaluationSuiteAuthoringService is not None
    assert EvaluationNetworkRuntimeGateway is not None
    assert AdaptiveEvaluatorModelGateway is not None
    assert ResumableEvaluationRunProcessor is not None
    assert ResumableEvaluationRunWorker is not None
    assert OutcomeAwareEvaluationRunProcessor is not None
    assert OutcomeAwareEvaluationRunWorker is not None
    assert ConcurrentOutcomeAwareEvaluationRunProcessor is not None
    assert ConcurrentOutcomeAwareEvaluationRunWorker is not None
    assert VariantAwareConcurrentEvaluationRunProcessor is not None
    assert VariantAwareConcurrentEvaluationRunWorker is not None
    assert EvaluationAuthoringWorker is not None
    assert EvaluationWorkerRegistry is not None
    assert register_evaluation_workers is not None


def test_evaluation_authoring_modules_import_cleanly() -> None:
    module_names = [
        "modules.evaluation.application.completed_service",
        "modules.evaluation.application.context_pack",
        "modules.evaluation.application.diagnostic_authoring",
        "modules.evaluation.application.durable_authoring",
        "modules.evaluation.application.enriched_service",
        "modules.evaluation.application.experience_service",
        "modules.evaluation.application.metering",
        "modules.evaluation.application.operational_service",
        "modules.evaluation.application.outcome_scoring",
        "modules.evaluation.application.secure_authoring",
        "modules.evaluation.application.suite_authoring",
        "modules.evaluation.application.token_budget",
        "modules.evaluation.domain.authoring_contract",
        "modules.evaluation.domain.contracts",
        "modules.evaluation.infra.adaptive_judge",
        "modules.evaluation.infra.budgeted_judge",
        "modules.evaluation.infra.generator",
        "modules.evaluation.infra.workers.authoring_worker",
        "modules.evaluation.infra.workers.concurrent_worker",
        "modules.evaluation.infra.workers.outcome_worker",
        "modules.evaluation.infra.workers.variant_worker",
        "modules.evaluation.presentation.authoring_routes",
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
        VariantAwareConcurrentEvaluationRunWorker.__new__(
            VariantAwareConcurrentEvaluationRunWorker
        ),
        WorkerProtocol,
    )
    assert isinstance(
        EvaluationAuthoringWorker.__new__(EvaluationAuthoringWorker),
        WorkerProtocol,
    )
