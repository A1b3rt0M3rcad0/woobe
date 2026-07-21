from modules.evaluation.application.hardened_service import (
    HardenedEvaluationApplicationService,
)
from modules.evaluation.application.runtime_gateway import (
    EvaluationNetworkRuntimeGateway,
)
from modules.evaluation.infra.workers.registry import (
    EvaluationWorkerRegistry,
    register_evaluation_workers,
)
from modules.evaluation.infra.workers.run_worker import (
    ResumableEvaluationRunProcessor,
    ResumableEvaluationRunWorker,
)
from modules.network.application.agent_invoker import ProjectRAIAgentInvoker
from modules.network.infra.runtime import (
    ProjectRAIAgentInvoker as CanonicalProjectRAIAgentInvoker,
)
from shared.workers.discovery import discover_module_entries


def test_network_agent_invoker_compatibility_import_is_canonical() -> None:
    assert ProjectRAIAgentInvoker is CanonicalProjectRAIAgentInvoker


def test_evaluation_module_imports_are_resolvable() -> None:
    assert HardenedEvaluationApplicationService is not None
    assert EvaluationNetworkRuntimeGateway is not None
    assert ResumableEvaluationRunProcessor is not None
    assert ResumableEvaluationRunWorker is not None
    assert EvaluationWorkerRegistry is not None
    assert register_evaluation_workers is not None


def test_evaluation_worker_registry_is_discoverable() -> None:
    entries = discover_module_entries()
    evaluation = next(item for item in entries if item.module_name == "evaluation")

    assert evaluation.registry_class is EvaluationWorkerRegistry
    assert evaluation.register_func is register_evaluation_workers
