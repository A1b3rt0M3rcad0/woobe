from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AGENT_ROOT = ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent"
EXECUTION_ROOT = AGENT_ROOT / "infra" / "execution"
STRATEGIES_ROOT = EXECUTION_ROOT / "strategies"
SDK_ROOT = AGENT_ROOT / "application" / "strategy_sdk"
RESOLVER = STRATEGIES_ROOT / "resolver.py"


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


def _strategy_files() -> list[Path]:
    return sorted(
        path
        for path in STRATEGIES_ROOT.glob("*.py")
        if path.name not in {"__init__.py", "resolver.py"}
    )


def test_execution_strategies_are_flat_one_file_extensions() -> None:
    nested_python = [
        path.relative_to(ROOT).as_posix()
        for path in STRATEGIES_ROOT.rglob("*.py")
        if path.parent != STRATEGIES_ROOT
    ]
    assert not nested_python, (
        "Execution Strategies must be one-file extensions; nested Strategy packages are "
        "not allowed: " + ", ".join(nested_python)
    )
    assert _strategy_files(), "At least one concrete Execution Strategy must exist"


def test_every_concrete_strategy_uses_strict_import_allowlist() -> None:
    allowed_prefixes = (
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "modules.agent.application.strategy_sdk",
        "modules.agent.application.interfaces.execution",
        "modules.agent.application.interfaces.execution_strategy",
    )
    violations: list[str] = []
    for path in _strategy_files():
        for module in _imports(path):
            if not any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in allowed_prefixes
            ):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, (
        "Concrete Execution Strategies may only depend on the shared Strategy API and "
        "stable Application interfaces:\n" + "\n".join(violations)
    )


def test_concrete_strategies_never_import_each_other() -> None:
    prefix = "modules.agent.infra.execution.strategies."
    violations: list[str] = []
    for path in _strategy_files():
        for module in _imports(path):
            if module.startswith(prefix):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "\n".join(violations)


def test_resolver_is_the_only_concrete_strategy_composition_point() -> None:
    concrete_modules = {
        f"modules.agent.infra.execution.strategies.{path.stem}"
        for path in _strategy_files()
    }
    allowed = {
        RESOLVER,
        EXECUTION_ROOT / "instrumented_execution_runner.py",
        EXECUTION_ROOT / "tool_execution_loop.py",
    }
    violations: list[str] = []
    for path in AGENT_ROOT.rglob("*.py"):
        if path in allowed or path in _strategy_files():
            continue
        imports = _imports(path)
        if any(
            module == concrete or module.startswith(concrete + ".")
            for module in imports
            for concrete in concrete_modules
        ):
            violations.append(path.relative_to(ROOT).as_posix())
    assert not violations, (
        "Concrete Strategy implementation leaked outside resolver or documented legacy "
        "facades: " + ", ".join(violations)
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
    assert methods == {"checkpoint"}


def test_concrete_strategy_does_not_reach_private_context_runtime_state() -> None:
    violations: list[str] = []
    for path in _strategy_files():
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Attribute):
                continue
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "ctx"
                and node.attr.startswith("_")
            ):
                violations.append(f"{path.name}: ctx.{node.attr}")
    assert not violations, "Strategy accessed private StrategyContext members: " + ", ".join(violations)


def test_concrete_strategy_state_does_not_own_runtime_recovery_plumbing() -> None:
    forbidden_methods = {
        "create",
        "checkpoint_cursor",
        "checkpoint_messages",
        "record_model_result",
        "record_tool_batch",
    }
    forbidden_symbols = {
        "StrategyInitialization",
        "StrategyResumeSnapshot",
    }
    violations: list[str] = []

    for path in _strategy_files():
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in forbidden_methods:
                    violations.append(f"{path.name}: method {node.name}")
            if isinstance(node, ast.Name) and node.id in forbidden_symbols:
                violations.append(f"{path.name}: symbol {node.id}")

    assert not violations, (
        "Concrete Strategy state must contain algorithm data only; recovery, checkpoint "
        "serialization and runtime message progression belong to Strategy Runtime: "
        + ", ".join(violations)
    )


def test_strategy_sdk_has_no_concrete_strategy_names() -> None:
    concrete_names = {path.stem.lower() for path in _strategy_files()}
    violations: list[str] = []
    for path in SDK_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for name in concrete_names:
            if f'"{name}"' in text or f"'{name}'" in text:
                violations.append(f"{path.relative_to(ROOT)} encodes {name}")
    assert not violations, "\n".join(violations)
