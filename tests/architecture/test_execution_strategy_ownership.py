from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXECUTION = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "infra"
    / "execution"
)
RUNNER = EXECUTION / "strategy_runtime" / "runner.py"
ASK_USE_CASE = EXECUTION / "ask_use_case.py"
STANDARD = EXECUTION / "strategies" / "standard.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is missing")


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_post_strategy_result_finalizer_does_not_exist() -> None:
    path = EXECUTION / "capabilities" / "result_finalization.py"
    assert not path.exists()


def test_runner_does_not_execute_strategy_capabilities() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "_run_preflight" not in source
    assert "finalize_execution_result" not in source
    assert "repair_json_if_needed" not in source
    assert ".tools.execute_many(" not in source
    assert ".knowledge.retrieve(" not in source
    assert ".context.assemble(" not in source
    assert ".model.invoke(" not in source


def test_runner_has_no_async_work_after_strategy_returns() -> None:
    function = _function(_tree(RUNNER), "execute_strategy")
    strategy_statement_index = None
    for index, statement in enumerate(function.body):
        if any(
            isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
            and _call_name(node.value) == "execute"
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "strategy"
            for node in ast.walk(statement)
        ):
            strategy_statement_index = index
            break

    assert strategy_statement_index is not None
    trailing = function.body[strategy_statement_index + 1 :]
    async_calls = [
        node
        for statement in trailing
        for node in ast.walk(statement)
        if isinstance(node, ast.Await)
    ]
    assert not async_calls, (
        "After ExecutionStrategy returns, runner finalization must be synchronous "
        "bookkeeping only; no capability may execute."
    )


def test_production_runtime_does_not_compose_legacy_fallback_mixin() -> None:
    path = EXECUTION / "structured_output_ask_use_case.py"
    source = path.read_text(encoding="utf-8")

    assert "InstrumentedFallbackMixin" not in source


def test_ask_use_case_does_not_orchestrate_fallback() -> None:
    function = _function(_tree(ASK_USE_CASE), "_execute_phased")
    fallback_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and _call_name(node) == "_try_fallback"
    ]
    assert not fallback_calls, (
        "Fallback execution belongs to ExecutionStrategy through StrategyModel."
    )


def test_standard_strategy_owns_bootstrap_fallback_and_output_repair() -> None:
    source = STANDARD.read_text(encoding="utf-8")

    assert "ctx.bootstrap.initial_tool_call" in source
    assert "ctx.tools.execute_many" in source
    assert "ctx.model.invoke_fallback" in source
    assert "ctx.output.requires_repair" in source
    assert "ctx.output.repair" in source
