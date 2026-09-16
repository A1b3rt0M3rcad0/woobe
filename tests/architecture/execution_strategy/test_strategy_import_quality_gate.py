from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AGENT_ROOT = ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent"
EXECUTION_ROOT = AGENT_ROOT / "infra" / "execution"
STRATEGIES_ROOT = EXECUTION_ROOT / "strategies"
SDK_ROOT = AGENT_ROOT / "application" / "strategy_sdk"
STANDARD_ROOT = STRATEGIES_ROOT / "standard"
RESOLVER = STRATEGIES_ROOT / "resolver.py"
LEGACY_RUNNER = EXECUTION_ROOT / "instrumented_execution_runner.py"
LEGACY_LOOP = EXECUTION_ROOT / "tool_execution_loop.py"


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


def test_concrete_strategy_import_allowlist() -> None:
    allowed_prefixes = (
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "modules.agent.application.strategy_sdk",
        "modules.agent.application.interfaces.execution",
        "modules.agent.application.interfaces.execution_strategy",
        "modules.agent.infra.execution.strategies.standard",
    )
    checked = (
        STANDARD_ROOT / "strategy.py",
        STANDARD_ROOT / "state.py",
        STANDARD_ROOT / "policy.py",
        STANDARD_ROOT / "phases.py",
        STANDARD_ROOT / "definition.py",
    )
    violations: list[str] = []
    for path in checked:
        for module in _imports(path):
            if not any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in allowed_prefixes
            ):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, (
        "Concrete Execution Strategies may only depend on the Strategy SDK, stable "
        "application interfaces and their own package:\n" + "\n".join(violations)
    )


def test_concrete_strategy_composition_is_limited_to_explicit_boundaries() -> None:
    concrete_prefix = "modules.agent.infra.execution.strategies.standard"
    allowed = {
        RESOLVER,
        LEGACY_RUNNER,
        LEGACY_LOOP,
        STANDARD_ROOT / "__init__.py",
        STANDARD_ROOT / "strategy.py",
        STANDARD_ROOT / "state.py",
        STANDARD_ROOT / "policy.py",
        STANDARD_ROOT / "phases.py",
        STANDARD_ROOT / "definition.py",
        STANDARD_ROOT / "compat.py",
    }
    violations: list[str] = []
    for path in AGENT_ROOT.rglob("*.py"):
        if path in allowed:
            continue
        if any(module.startswith(concrete_prefix) for module in _imports(path)):
            violations.append(path.relative_to(ROOT).as_posix())
    assert not violations, (
        "Concrete Strategy implementation leaked outside its package, resolver or "
        "documented compatibility facades: " + ", ".join(violations)
    )


def test_strategy_sdk_context_public_surface_stays_small() -> None:
    path = SDK_ROOT / "context.py"
    tree = _tree(path)
    context = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "StrategyContext"
    )
    methods = {
        node.name
        for node in context.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert methods == {"checkpoint", "complete", "suspend"}


def test_concrete_strategy_does_not_reach_private_context_runtime_state() -> None:
    path = STANDARD_ROOT / "strategy.py"
    violations: list[str] = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Attribute):
            continue
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "ctx"
            and node.attr.startswith("_")
        ):
            violations.append(node.attr)
    assert not violations, f"Strategy accessed private StrategyContext members: {violations}"


def test_strategy_sdk_has_no_concrete_strategy_names() -> None:
    forbidden = ("standard", "planner", "react", "reflection")
    violations: list[str] = []
    for path in SDK_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for name in forbidden:
            if f'"{name}"' in text or f"'{name}'" in text:
                violations.append(f"{path.relative_to(ROOT)} encodes {name}")
    assert not violations, "\n".join(violations)
