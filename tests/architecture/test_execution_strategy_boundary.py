from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent"
NETWORK_ROOT = ROOT / "packages" / "woobe-core" / "src" / "modules" / "network"
EXECUTION_ROOT = AGENT_ROOT / "infra" / "execution"
CAPABILITIES_ROOT = EXECUTION_ROOT / "capabilities"
STRATEGIES_ROOT = EXECUTION_ROOT / "strategies"
STANDARD_STRATEGY = STRATEGIES_ROOT / "standard.py"
RESOLVER = STRATEGIES_ROOT / "resolver.py"
PRIMARY_RUNTIME = EXECUTION_ROOT / "instrumented_primary_mixin.py"
RUNTIME_FACTORY = AGENT_ROOT / "composition" / "factories" / "ask_agent_runtime_factory.py"
ASK_JOB_WORKER = (
    ROOT
    / "packages"
    / "woobe-workers"
    / "src"
    / "woobe_workers"
    / "consumers"
    / "agent"
    / "ask_job_worker.py"
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports_module(path: Path, module: str, name: str | None = None) -> bool:
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            if name is None or any(alias.name == name for alias in node.names):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == module for alias in node.names):
                return True
    return False


def _calls(path: Path, method_name: str) -> bool:
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == method_name:
            return True
        if isinstance(node.func, ast.Name) and node.func.id == method_name:
            return True
    return False


def test_execution_strategy_partition_is_explicit() -> None:
    assert STRATEGIES_ROOT.is_dir()
    assert CAPABILITIES_ROOT.is_dir()
    assert (STRATEGIES_ROOT / "README.md").is_file()
    assert STANDARD_STRATEGY.is_file()
    assert RESOLVER.is_file()
    assert (CAPABILITIES_ROOT / "preparation.py").is_file()
    assert (CAPABILITIES_ROOT / "result_finalization.py").is_file()
    assert (
        AGENT_ROOT / "application" / "interfaces" / "execution_strategy.py"
    ).is_file()


def test_strategies_do_not_depend_on_legacy_instrumented_runner() -> None:
    module = "modules.agent.infra.execution.instrumented_execution_runner"
    violations: list[str] = []

    for path in STRATEGIES_ROOT.rglob("*.py"):
        if _imports_module(path, module, "run_instrumented_execution"):
            violations.append(path.relative_to(ROOT).as_posix())

    assert not violations, (
        "Execution Strategies must compose reusable capabilities instead of the legacy "
        "instrumented runner: " + ", ".join(violations)
    )


def test_standard_strategy_composes_shared_execution_capabilities() -> None:
    assert _imports_module(
        STANDARD_STRATEGY,
        "modules.agent.infra.execution.capabilities.preparation",
        "prepare_execution",
    )
    assert _imports_module(
        STANDARD_STRATEGY,
        "modules.agent.infra.execution.capabilities.result_finalization",
        "finalize_execution_result",
    )


def test_standard_strategy_is_only_composed_by_strategy_resolver() -> None:
    module = "modules.agent.infra.execution.strategies.standard"
    violations: list[str] = []

    for path in AGENT_ROOT.rglob("*.py"):
        if path in {STANDARD_STRATEGY, RESOLVER}:
            continue
        if _imports_module(path, module):
            violations.append(path.relative_to(ROOT).as_posix())

    assert not violations, (
        "Concrete StandardExecutionStrategy leaked outside the resolver: "
        + ", ".join(violations)
    )


def test_primary_runtime_does_not_compose_concrete_strategy_resolver() -> None:
    assert not _imports_module(
        PRIMARY_RUNTIME,
        "modules.agent.infra.execution.strategies.resolver",
    )


def test_network_remains_agnostic_to_agent_execution_strategy() -> None:
    forbidden_fragments = (
        "modules.agent.application.interfaces.execution_strategy",
        "modules.agent.application.execution_strategy_config",
        "modules.agent.infra.execution.strategies",
    )
    violations: list[str] = []

    for path in NETWORK_ROOT.rglob("*.py"):
        tree = _tree(path)
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            for module in modules:
                if any(module.startswith(prefix) for prefix in forbidden_fragments):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports {module}"
                    )

    assert not violations, "\n".join(violations)


def test_production_agent_runtime_configures_strategy_resolver() -> None:
    assert _calls(RUNTIME_FACTORY, "configure_execution_strategy_resolver")


def test_background_agent_worker_configures_strategy_resolver() -> None:
    assert _calls(ASK_JOB_WORKER, "configure_execution_strategy_resolver")


def test_execution_strategy_names_are_not_versioned() -> None:
    config_path = AGENT_ROOT / "application" / "execution_strategy_config.py"
    content = config_path.read_text(encoding="utf-8")

    assert 'DEFAULT_EXECUTION_STRATEGY = "standard"' in content
    assert "standard:v1" not in content
    assert "strategy_version" not in content
