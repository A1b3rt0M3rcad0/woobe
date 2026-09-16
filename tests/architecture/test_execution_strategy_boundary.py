from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent"
NETWORK_ROOT = ROOT / "packages" / "woobe-core" / "src" / "modules" / "network"
APPLICATION_ROOT = AGENT_ROOT / "application"
SDK_ROOT = APPLICATION_ROOT / "strategy_sdk"
EXECUTION_ROOT = AGENT_ROOT / "infra" / "execution"
CAPABILITIES_ROOT = EXECUTION_ROOT / "capabilities"
STRATEGY_RUNTIME_ROOT = EXECUTION_ROOT / "strategy_runtime"
STRATEGIES_ROOT = EXECUTION_ROOT / "strategies"
STANDARD_PACKAGE = STRATEGIES_ROOT / "standard"
STANDARD_STRATEGY = STANDARD_PACKAGE / "strategy.py"
STANDARD_STATE = STANDARD_PACKAGE / "state.py"
STANDARD_POLICY = STANDARD_PACKAGE / "policy.py"
STANDARD_PHASES = STANDARD_PACKAGE / "phases.py"
STANDARD_DEFINITION = STANDARD_PACKAGE / "definition.py"
STANDARD_COMPAT = STANDARD_PACKAGE / "compat.py"
RESOLVER = STRATEGIES_ROOT / "resolver.py"
STRATEGY_INTERFACE = APPLICATION_ROOT / "interfaces" / "execution_strategy.py"
STRATEGY_CONFIG = APPLICATION_ROOT / "execution_strategy_config.py"
STRATEGY_REGISTRY = APPLICATION_ROOT / "execution_strategy_registry.py"
MODEL_CAPABILITY = CAPABILITIES_ROOT / "model_invocation.py"
TOOL_CAPABILITY = CAPABILITIES_ROOT / "tool_execution.py"
RECOVERY_CAPABILITY = CAPABILITIES_ROOT / "recovery.py"
LEGACY_LOOP = EXECUTION_ROOT / "tool_execution_loop.py"
LEGACY_RUNNER = EXECUTION_ROOT / "instrumented_execution_runner.py"
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


def _imports(path: Path) -> list[str]:
    result: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module:
            result.append(node.module)
        elif isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
    return result


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
    assert SDK_ROOT.is_dir()
    assert STRATEGY_RUNTIME_ROOT.is_dir()
    assert STRATEGIES_ROOT.is_dir()
    assert STANDARD_PACKAGE.is_dir()
    for path in (
        SDK_ROOT / "context.py",
        SDK_ROOT / "model.py",
        SDK_ROOT / "tools.py",
        SDK_ROOT / "outcome.py",
        SDK_ROOT / "state.py",
        STRATEGY_RUNTIME_ROOT / "builder.py",
        STRATEGY_RUNTIME_ROOT / "context.py",
        STRATEGY_RUNTIME_ROOT / "model.py",
        STRATEGY_RUNTIME_ROOT / "tools.py",
        STRATEGY_RUNTIME_ROOT / "checkpoint.py",
        STRATEGY_RUNTIME_ROOT / "runtime_state.py",
        STRATEGY_RUNTIME_ROOT / "runner.py",
        STANDARD_STRATEGY,
        STANDARD_STATE,
        STANDARD_POLICY,
        STANDARD_PHASES,
        STANDARD_DEFINITION,
        STANDARD_COMPAT,
        RESOLVER,
        STRATEGY_INTERFACE,
    ):
        assert path.is_file(), path


def test_strategy_sdk_never_depends_on_infrastructure_or_provider_frameworks() -> None:
    forbidden = (
        "modules.agent.infra",
        "modules.network",
        "woobe_api",
        "woobe_workers",
        "langchain",
        "openai",
        "anthropic",
        "sqlalchemy",
        "redis",
        "pymongo",
    )
    violations: list[str] = []
    for path in SDK_ROOT.rglob("*.py"):
        for module in _imports(path):
            if any(module.startswith(prefix) for prefix in forbidden):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "\n".join(violations)


def test_concrete_standard_algorithm_uses_sdk_not_runtime_implementation() -> None:
    forbidden = (
        "modules.agent.infra.execution.capabilities",
        "modules.agent.infra.execution.strategy_runtime",
        "modules.agent.infra.database",
        "modules.agent.infra.execution.runtime_streaming",
        "modules.agent.infra.execution.durable_execution_instrumentation",
        "modules.network",
        "woobe_api",
        "woobe_workers",
        "langchain",
        "openai",
        "anthropic",
    )
    checked = (STANDARD_STRATEGY, STANDARD_STATE, STANDARD_POLICY, STANDARD_PHASES, STANDARD_DEFINITION)
    violations: list[str] = []
    for path in checked:
        for module in _imports(path):
            if any(module.startswith(prefix) for prefix in forbidden):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "\n".join(violations)
    assert _imports_module(
        STANDARD_STRATEGY,
        "modules.agent.application.strategy_sdk",
        "StrategyContext",
    )
    assert _calls(STANDARD_STRATEGY, "checkpoint")
    assert _calls(STANDARD_STRATEGY, "execute_many")
    assert _calls(STANDARD_STRATEGY, "invoke")


def test_strategy_runtime_is_the_only_bridge_to_capabilities() -> None:
    assert any(
        module.startswith("modules.agent.infra.execution.capabilities")
        for path in STRATEGY_RUNTIME_ROOT.rglob("*.py")
        for module in _imports(path)
    )
    forbidden = "modules.agent.infra.execution.strategy_runtime"
    violations: list[str] = []
    for path in CAPABILITIES_ROOT.rglob("*.py"):
        if any(module.startswith(forbidden) for module in _imports(path)):
            violations.append(path.relative_to(ROOT).as_posix())
    assert not violations, "Capabilities must not depend on Strategy Runtime: " + ", ".join(violations)


def test_strategy_runtime_never_depends_on_concrete_strategies() -> None:
    violations: list[str] = []
    prefix = "modules.agent.infra.execution.strategies"
    for path in STRATEGY_RUNTIME_ROOT.rglob("*.py"):
        for module in _imports(path):
            if module.startswith(prefix):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "\n".join(violations)


def test_resolver_is_explicit_composition_point() -> None:
    assert _imports_module(
        RESOLVER,
        "modules.agent.application.interfaces.execution_strategy",
        "ExecutionStrategyResolver",
    )
    assert _imports_module(
        RESOLVER,
        "modules.agent.infra.execution.strategies.standard",
        "build_standard_strategy_definition",
    )
    assert not _imports_module(RESOLVER, "modules.agent.application.execution_strategy_registry")
    assert not _imports_module(RESOLVER, "modules.agent.application.execution_strategy_config")


def test_product_registry_does_not_import_concrete_strategy_implementation() -> None:
    for module in _imports(STRATEGY_REGISTRY):
        assert not module.startswith("modules.agent.infra.execution.strategies")
        assert not module.startswith("modules.agent.infra.execution.strategy_runtime")


def test_model_and_tool_capabilities_keep_durable_instrumentation() -> None:
    durable_module = "modules.agent.infra.execution.durable_execution_instrumentation"
    assert _imports_module(MODEL_CAPABILITY, durable_module, "invoke_llm")
    assert _imports_module(TOOL_CAPABILITY, durable_module, "execute_tool_call")


def test_recovery_capability_remains_strategy_neutral() -> None:
    checkpoint_module = "modules.agent.infra.execution.agent_recovery_checkpoint"
    assert _imports_module(
        RECOVERY_CAPABILITY,
        checkpoint_module,
        "checkpoint_strategy_boundary",
    )
    assert _imports_module(
        RECOVERY_CAPABILITY,
        checkpoint_module,
        "load_strategy_execution_resume",
    )
    for module in _imports(RECOVERY_CAPABILITY):
        assert not module.startswith("modules.agent.infra.execution.strategies.standard")


def test_legacy_entrypoints_delegate_to_new_strategy_runtime() -> None:
    assert _imports_module(
        LEGACY_RUNNER,
        "modules.agent.infra.execution.strategy_runtime.runner",
        "execute_strategy_definition",
    )
    assert _imports_module(
        LEGACY_LOOP,
        "modules.agent.infra.execution.strategies.standard",
        "run_standard_strategy_loop",
    )


def test_primary_runtime_does_not_know_concrete_strategy_implementation() -> None:
    forbidden = (
        "modules.agent.infra.execution.strategies.standard",
        "modules.agent.infra.execution.strategies.resolver",
        "modules.agent.infra.execution.strategy_runtime",
    )
    for module in _imports(PRIMARY_RUNTIME):
        assert not any(module.startswith(prefix) for prefix in forbidden)


def test_network_remains_agnostic_to_agent_execution_strategy() -> None:
    forbidden_fragments = (
        "modules.agent.application.interfaces.execution_strategy",
        "modules.agent.application.strategy_sdk",
        "modules.agent.application.execution_strategy_config",
        "modules.agent.application.execution_strategy_registry",
        "modules.agent.infra.execution.strategies",
        "modules.agent.infra.execution.strategy_runtime",
    )
    violations: list[str] = []
    for path in NETWORK_ROOT.rglob("*.py"):
        for module in _imports(path):
            if any(module.startswith(prefix) for prefix in forbidden_fragments):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "\n".join(violations)


def test_production_composition_configures_strategy_resolver() -> None:
    assert _calls(RUNTIME_FACTORY, "configure_execution_strategy_resolver")
    assert _calls(ASK_JOB_WORKER, "configure_execution_strategy_resolver")


def test_execution_strategy_names_are_not_versioned() -> None:
    registry = STRATEGY_REGISTRY.read_text(encoding="utf-8")
    config = STRATEGY_CONFIG.read_text(encoding="utf-8")
    resolver = RESOLVER.read_text(encoding="utf-8")
    assert 'DEFAULT_EXECUTION_STRATEGY = "standard"' in registry
    assert "standard:v1" not in registry
    assert "standard:v1" not in config
    assert "standard:v1" not in resolver
    assert "strategy_version" not in registry
    assert "strategy_version" not in config
