from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
)
AGENT_EXECUTION = AGENT_ROOT / "infra" / "execution"
AGENT_RUNTIME_FACTORY = (
    AGENT_ROOT
    / "composition"
    / "factories"
    / "ask_agent_runtime_factory.py"
)
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
_CONTEXT_ASSEMBLY = AGENT_ROOT / "application" / "context_assembly.py"
_CONTEXT_MANAGER_CONTRACT = (
    AGENT_ROOT / "application" / "interfaces" / "context_manager.py"
)
_CONTEXT_MANAGERS_ROOT = AGENT_ROOT / "application" / "context_managers"
_CONTEXT_MANAGERS_README = _CONTEXT_MANAGERS_ROOT / "README.md"
_STANDARD_ASSEMBLER = _CONTEXT_MANAGERS_ROOT / "standard.py"
_CONTEXT_MANAGER_REGISTRY = (
    AGENT_ROOT / "application" / "context_manager_registry.py"
)
_STANDARD_ASSEMBLER_MODULE = "modules.agent.application.context_managers.standard"
_CONTEXT_MANAGER_REGISTRY_MODULE = (
    "modules.agent.application.context_manager_registry"
)
_BACKGROUND_BOUNDARY_MODULE = "modules.agent.background_boundary"
_LEGACY_ASSEMBLY_MODULE = "modules.agent.application.context_assembly"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _environment_reads(tree: ast.AST) -> set[str]:
    fields: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "environment"
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            fields.add(node.args[1].value)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "environment"
            and isinstance(node.ctx, ast.Load)
        ):
            fields.add(node.attr)
    return fields


def _environment_contract_fields(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ContextInvocationEnvironment":
            return {
                member.target.id
                for member in node.body
                if isinstance(member, ast.AnnAssign)
                and isinstance(member.target, ast.Name)
            }
    raise AssertionError("ContextInvocationEnvironment contract is missing")


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _has_keyword(node: ast.Call, keyword: str) -> bool:
    return any(item.arg == keyword for item in node.keywords)


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if (
                    isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and member.name == name
                ):
                    return member
    raise AssertionError(f"Function {name} is missing")


def _assigned_constructor_names(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    constructor_name: str,
) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(function):
        value = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if not isinstance(value, ast.Call) or _call_name(value) != constructor_name:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _context_manager_configured_names(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "configure_context_manager":
            continue
        if isinstance(node.func.value, ast.Name):
            names.add(node.func.value.id)
    return names


def test_context_manager_strategy_partition_is_explicit() -> None:
    assert _CONTEXT_MANAGERS_ROOT.is_dir()
    assert _CONTEXT_MANAGERS_README.is_file()
    assert _STANDARD_ASSEMBLER.is_file()
    assert not (AGENT_ROOT / "application" / "standard_context_assembler.py").exists()


def test_agent_execution_depends_only_on_context_assembler_contract() -> None:
    violations: list[str] = []

    forbidden_modules = {
        _STANDARD_ASSEMBLER_MODULE,
        _CONTEXT_MANAGER_REGISTRY_MODULE,
    }
    for path in AGENT_EXECUTION.rglob("*.py"):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom):
                if node.module in forbidden_modules:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports {node.module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_modules:
                        violations.append(
                            f"{path.relative_to(ROOT).as_posix()} imports {alias.name}"
                        )

    assert not violations, "\n".join(violations)


def test_standard_context_assembler_is_composed_only_by_application_registry() -> None:
    violations: list[str] = []

    for path in AGENT_ROOT.rglob("*.py"):
        if path in {_STANDARD_ASSEMBLER, _CONTEXT_MANAGER_REGISTRY}:
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom):
                if node.module == _STANDARD_ASSEMBLER_MODULE:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports StandardContextAssembler"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == _STANDARD_ASSEMBLER_MODULE:
                        violations.append(
                            f"{path.relative_to(ROOT).as_posix()} imports StandardContextAssembler"
                        )

    assert not violations, "\n".join(violations)


def test_legacy_assemble_context_is_only_consumed_by_standard_adapter() -> None:
    violations: list[str] = []

    for path in AGENT_ROOT.rglob("*.py"):
        if path == _STANDARD_ASSEMBLER:
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom):
                if node.module == _LEGACY_ASSEMBLY_MODULE and any(
                    alias.name == "assemble_context" for alias in node.names
                ):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports assemble_context directly"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == _LEGACY_ASSEMBLY_MODULE:
                        violations.append(
                            f"{path.relative_to(ROOT).as_posix()} imports context_assembly module directly"
                        )

    assert not violations, "\n".join(violations)


def test_context_invocation_environment_covers_every_context_assembly_read() -> None:
    required = _environment_reads(_tree(_CONTEXT_ASSEMBLY))
    declared = _environment_contract_fields(_tree(_CONTEXT_MANAGER_CONTRACT))
    missing = sorted(required - declared)

    assert not missing, (
        "ContextInvocationEnvironment is missing fields read by context_assembly.py: "
        + ", ".join(missing)
    )
    source = _CONTEXT_ASSEMBLY.read_text(encoding="utf-8")
    assert "current_execution" not in source
    assert "ContextAssemblyRuntimeContext" not in _CONTEXT_MANAGER_CONTRACT.read_text(
        encoding="utf-8"
    )


def test_execution_preparation_cannot_retrieve_knowledge() -> None:
    prepare_paths = (
        AGENT_EXECUTION / "ask_use_case.py",
        AGENT_EXECUTION / "explicit_runtime_persistence.py",
        AGENT_EXECUTION / "transaction_bounded_structured_output.py",
        AGENT_EXECUTION / "agent_run_recovery_runtime.py",
    )
    violations: list[str] = []

    for path in prepare_paths:
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if "prepare" not in node.name:
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                if _call_name(call) == "_load_rag_context":
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}::{node.name} "
                        "retrieves Knowledge during preparation"
                    )
                if (
                    isinstance(call.func, ast.Attribute)
                    and call.func.attr == "retrieve"
                    and isinstance(call.func.value, ast.Attribute)
                    and call.func.value.attr == "_rag_runtime"
                ):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}::{node.name} "
                        "calls RAG runtime retrieval during preparation"
                    )

    legacy_base = (AGENT_EXECUTION / "ask_use_case.py").read_text(encoding="utf-8")
    assert "_load_rag_context" not in legacy_base
    assert not (AGENT_EXECUTION / "transaction_bounded_rag.py").exists()
    assert "Use the following context when relevant." not in legacy_base
    assert not violations, "\n".join(violations)


def test_tool_instructions_are_invocation_scoped_not_prepare_scoped() -> None:
    preparation = AGENT_EXECUTION / "capabilities" / "preparation.py"
    prepare_function = _find_function(_tree(preparation), "prepare_execution")
    forbidden_calls = {
        "_messages_with_bound_capability_authority",
        "_messages_with_tool_grounding",
        "_messages_with_skill_usage",
    }

    called = {
        name
        for node in ast.walk(prepare_function)
        if isinstance(node, ast.Call)
        and (name := _call_name(node)) in forbidden_calls
    }
    assert not called, (
        "prepare_execution must not materialize invocation-scoped Tool instructions: "
        + ", ".join(sorted(called))
    )

    for filename in (
        "structured_output_ask_use_case.py",
        "transaction_bounded_structured_output.py",
        "agent_run_recovery_runtime.py",
    ):
        source = (AGENT_EXECUTION / filename).read_text(encoding="utf-8")
        assert "_TOOL_GROUNDING_RUNTIME_RULES" not in source, (
            f"{filename} still materializes Tool grounding during preparation"
        )



def test_strategy_runtime_context_facade_does_not_own_context_policy() -> None:
    runtime_context = (
        AGENT_EXECUTION / "strategy_runtime" / "context_manager.py"
    ).read_text(encoding="utf-8")
    forbidden = {
        "_KNOWLEDGE_PREAMBLE",
        "_messages_with_bound_capability_authority",
        "_messages_with_tool_grounding",
        "_messages_with_skill_usage",
        "materialize_context_contributions",
    }
    leaked = sorted(name for name in forbidden if name in runtime_context)
    assert not leaked, (
        "Strategy Runtime must transport Context state, not define Context policy: "
        + ", ".join(leaked)
    )

    standard_manager = _STANDARD_ASSEMBLER.read_text(encoding="utf-8")
    assert "_prepare_invocation_messages(request)" in standard_manager
    assert "request.contributions" in standard_manager
    assert "request.environment.active_tool_definitions" in standard_manager


def test_every_model_invocation_has_explicit_context_boundary() -> None:
    violations: list[str] = []

    for path in AGENT_EXECUTION.rglob("*.py"):
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == "invoke_llm":
                if _has_keyword(node, "context_assembler"):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} calls invoke_llm(...) "
                        "with the forbidden context_assembler compatibility path"
                    )
                if not _has_keyword(node, "context_prepared"):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} calls invoke_llm(...) "
                        "without an explicitly prepared Context"
                    )
            elif name in {"run_tool_loop", "run_instrumented_execution"}:
                if not _has_keyword(node, "context_assembler"):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} calls {name}(...) "
                        "without context_assembler"
                    )
            elif name == "repair_json_if_needed":
                if not _has_keyword(node, "context_capability"):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} calls repair_json_if_needed(...) "
                        "without context_capability"
                    )

    assert not violations, "\n".join(violations)


def test_model_instrumentation_does_not_own_context_assembly() -> None:
    path = AGENT_EXECUTION / "execution_instrumentation.py"
    source = path.read_text(encoding="utf-8")
    imports: list[str] = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)

    assert "modules.agent.application.interfaces.context_assembler" not in imports
    assert "_assemble_invocation_context" not in source
    assert "context_assembler" not in source


def test_model_invocation_capability_does_not_own_context_assembly() -> None:
    path = AGENT_EXECUTION / "capabilities" / "model_invocation.py"
    source = path.read_text(encoding="utf-8")
    imports = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)

    assert "modules.agent.application.interfaces.context_assembler" not in imports
    assert "ContextAssembler" not in source
    assert "context_assembler" not in source


def test_special_model_paths_use_explicit_context_and_model_capabilities() -> None:
    for filename in (
        "instrumented_fallback_mixin.py",
        "structured_json_repair.py",
    ):
        path = AGENT_EXECUTION / filename
        source = path.read_text(encoding="utf-8")

        assert "ModelInvocationCapability" in source
        assert "invoke_llm(" not in source
        assert "context_prepared=True" in source
        assert "ContextAssemblyCapability" in source


def test_background_worker_gets_runtime_dispatcher_only_from_public_boundary() -> None:
    boundary_names: set[str] = set()
    direct_standard_imports: list[str] = []
    direct_registry_imports: list[str] = []

    for node in ast.walk(_tree(ASK_JOB_WORKER)):
        if not isinstance(node, ast.ImportFrom):
            continue
        names = {alias.name for alias in node.names}
        if node.module == _BACKGROUND_BOUNDARY_MODULE:
            boundary_names.update(names)
        if "StandardContextAssembler" in names:
            direct_standard_imports.append(str(node.module))
        if node.module == _CONTEXT_MANAGER_REGISTRY_MODULE:
            direct_registry_imports.append(str(node.module))

    assert "build_runtime_context_manager" in boundary_names, (
        "AskJobWorker must obtain the snapshot-aware ContextAssembler through "
        "modules.agent.background_boundary"
    )
    assert not direct_standard_imports, (
        "AskJobWorker must not import StandardContextAssembler directly: "
        + ", ".join(direct_standard_imports)
    )
    assert not direct_registry_imports, (
        "AskJobWorker must not bypass Agent background boundary for the registry: "
        + ", ".join(direct_registry_imports)
    )


def test_production_runtime_composition_configures_context_assembler_explicitly() -> None:
    cases = [
        (
            AGENT_RUNTIME_FACTORY,
            "_build_agent_runtime",
            "FrozenSnapshotStructuredOutputRuntime",
        ),
        (
            ASK_JOB_WORKER,
            "_process_job",
            "TransactionBoundedStructuredOutputRuntime",
        ),
    ]
    violations: list[str] = []

    for path, function_name, constructor_name in cases:
        function = _find_function(_tree(path), function_name)
        constructed = _assigned_constructor_names(function, constructor_name)
        configured = _context_manager_configured_names(function)
        if not constructed:
            violations.append(
                f"{path.relative_to(ROOT).as_posix()} no longer constructs "
                f"{constructor_name} in {function_name}"
            )
            continue
        for variable_name in sorted(constructed - configured):
            violations.append(
                f"{path.relative_to(ROOT).as_posix()} constructs {constructor_name} "
                f"as {variable_name} without configure_context_manager(...)"
            )

    assert not violations, "\n".join(violations)
