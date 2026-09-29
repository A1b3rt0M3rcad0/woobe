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
STRATEGY_OUTPUT = EXECUTION / "strategy_runtime" / "output.py"
STRATEGY_MODEL = EXECUTION / "strategy_runtime" / "model.py"
PREPARATION = EXECUTION / "capabilities" / "preparation.py"
RAG_CLASSIC = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "application"
    / "rag"
    / "strategies"
    / "classic.py"
)
RAG_KNOWLEDGE = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "application"
    / "rag"
    / "knowledge_strategy.py"
)
KNOWLEDGE_CAPABILITY = EXECUTION / "capabilities" / "knowledge_retrieval.py"
RAG_RUNTIME_ADAPTER = EXECUTION / "rag" / "runtime_adapter.py"
STRATEGY_KNOWLEDGE = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "application"
    / "strategy_sdk"
    / "knowledge.py"
)
RAG_INTERFACES = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "application"
    / "interfaces"
    / "rag.py"
)
RAG_CONFIG_DTOS = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "application"
    / "dtos"
    / "rag_config_dtos.py"
)


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



def test_strategy_output_does_not_own_model_plumbing() -> None:
    source = STRATEGY_OUTPUT.read_text(encoding="utf-8")

    forbidden = {
        "ModelInvocationCapability",
        "repair_json_if_needed",
        "create_chat_model",
        "_llm_factory",
        "_api_key",
        "_base_url",
        "_pricing_snapshot",
    }
    leaked = sorted(name for name in forbidden if name in source)
    assert not leaked, (
        "Strategy Output may define validation/repair policy but Model execution "
        "belongs to Strategy Model: " + ", ".join(leaked)
    )
    assert "invoke_structured_repair" in source


def test_strategy_model_owns_structured_repair_inference() -> None:
    source = STRATEGY_MODEL.read_text(encoding="utf-8")

    assert "def invoke_structured_repair" in source
    assert "_structured_repair_model_factory" in source
    assert "retain_terminal_result=True" in source


def test_execution_preparation_is_composed_from_focused_helpers() -> None:
    function = next(
        node
        for node in _tree(PREPARATION).body
        if isinstance(node, ast.FunctionDef) and node.name == "prepare_execution"
    )
    calls = {
        name
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and (name := _call_name(node)) is not None
    }

    required = {
        "_prepare_knowledge",
        "_prepare_tools",
        "_prepare_output_contract",
        "_prepare_models",
        "_prepare_fallback_model_factory",
        "_initialize_runtime_state",
    }
    assert required.issubset(calls)
    assert "create_chat_model" not in calls
    assert "_messages_with_leading_system_instruction" not in calls


def test_knowledge_owns_query_construction() -> None:
    standard_source = STANDARD.read_text(encoding="utf-8")
    classic_source = RAG_CLASSIC.read_text(encoding="utf-8")
    knowledge_strategy_source = RAG_KNOWLEDGE.read_text(encoding="utf-8")
    knowledge_capability_source = KNOWLEDGE_CAPABILITY.read_text(encoding="utf-8")
    adapter_source = RAG_RUNTIME_ADAPTER.read_text(encoding="utf-8")
    knowledge_source = STRATEGY_KNOWLEDGE.read_text(encoding="utf-8")
    rag_interfaces_source = RAG_INTERFACES.read_text(encoding="utf-8")
    rag_config_tree = _tree(RAG_CONFIG_DTOS)

    assert "_conversation_knowledge_query" not in standard_source
    assert "query_policy" not in standard_source
    assert "history_turns" not in standard_source
    assert "StrategyMessageRole" not in standard_source
    assert "ctx.knowledge.retrieve(" in standard_source
    assert "conversation=ctx.conversation" in standard_source

    assert "build_retrieval_query" not in classic_source
    assert "history_turns" not in classic_source
    assert "query_mode" not in classic_source
    assert "request.history" not in classic_source

    assert "def _build_query(" in knowledge_strategy_source
    assert "history_turns" in knowledge_strategy_source
    assert "query_mode" in knowledge_strategy_source
    assert "build_query" not in knowledge_capability_source
    assert "history_turns" not in knowledge_capability_source
    assert "query_mode" not in knowledge_capability_source

    assert "history:" not in adapter_source
    assert "history=" not in adapter_source
    assert "conversation: StrategyConversation" in knowledge_source
    assert "query_policy" not in knowledge_source
    assert "config: RAGRetrievalConfig" in rag_interfaces_source

    retrieval_config = next(
        node
        for node in rag_config_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RAGRetrievalConfig"
    )
    runtime_config = next(
        node
        for node in rag_config_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RAGRuntimeConfig"
    )
    retrieval_fields = {
        node.target.id
        for node in retrieval_config.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }
    runtime_fields = {
        node.target.id
        for node in runtime_config.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }

    assert "query_mode" not in retrieval_fields
    assert "history_turns" not in retrieval_fields
    assert {"query_mode", "history_turns"}.issubset(runtime_fields)
