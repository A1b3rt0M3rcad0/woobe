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
_CONTEXT_ASSEMBLER_CONTRACT = (
    AGENT_ROOT / "application" / "interfaces" / "context_assembler.py"
)
_CONTEXT_MANAGERS_ROOT = AGENT_ROOT / "application" / "context_managers"
_CONTEXT_MANAGERS_README = _CONTEXT_MANAGERS_ROOT / "README.md"
_STANDARD_ASSEMBLER = _CONTEXT_MANAGERS_ROOT / "standard.py"
_CONTEXT_ASSEMBLER_REGISTRY = (
    AGENT_ROOT / "application" / "context_assembler_registry.py"
)
_STANDARD_ASSEMBLER_MODULE = "modules.agent.application.context_managers.standard"
_CONTEXT_ASSEMBLER_REGISTRY_MODULE = (
    "modules.agent.application.context_assembler_registry"
)
_BACKGROUND_BOUNDARY_MODULE = "modules.agent.background_boundary"
_LEGACY_ASSEMBLY_MODULE = "modules.agent.application.context_assembly"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _runtime_context_reads(tree: ast.AST) -> set[str]:
    fields: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "runtime_context"
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            fields.add(node.args[1].value)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "runtime_context"
            and isinstance(node.ctx, ast.Load)
        ):
            fields.add(node.attr)
    return fields


def _runtime_context_contract_fields(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ContextAssemblyRuntimeContext":
            return {
                member.name
                for member in node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(
                    isinstance(decorator, ast.Name) and decorator.id == "property"
                    for decorator in member.decorator_list
                )
            }
    raise AssertionError("ContextAssemblyRuntimeContext contract is missing")


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


def _context_assembler_configured_names(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "configure_context_assembler":
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
        _CONTEXT_ASSEMBLER_REGISTRY_MODULE,
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
        if path in {_STANDARD_ASSEMBLER, _CONTEXT_ASSEMBLER_REGISTRY}:
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


def test_context_assembly_runtime_contract_covers_every_runtime_state_read() -> None:
    required = _runtime_context_reads(_tree(_CONTEXT_ASSEMBLY))
    declared = _runtime_context_contract_fields(_tree(_CONTEXT_ASSEMBLER_CONTRACT))
    missing = sorted(required - declared)

    assert not missing, (
        "ContextAssemblyRuntimeContext is missing fields read by context_assembly.py: "
        + ", ".join(missing)
    )


def test_every_model_invocation_propagates_context_assembler_explicitly() -> None:
    violations: list[str] = []

    for path in AGENT_EXECUTION.rglob("*.py"):
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name not in {
                "invoke_llm",
                "run_tool_loop",
                "repair_json_if_needed",
                "run_instrumented_execution",
            }:
                continue
            if not _has_keyword(node, "context_assembler"):
                violations.append(
                    f"{path.relative_to(ROOT).as_posix()} calls {name}(...) "
                    "without context_assembler"
                )

    assert not violations, "\n".join(violations)


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
        if node.module == _CONTEXT_ASSEMBLER_REGISTRY_MODULE:
            direct_registry_imports.append(str(node.module))

    assert "build_runtime_context_assembler" in boundary_names, (
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
        configured = _context_assembler_configured_names(function)
        if not constructed:
            violations.append(
                f"{path.relative_to(ROOT).as_posix()} no longer constructs "
                f"{constructor_name} in {function_name}"
            )
            continue
        for variable_name in sorted(constructed - configured):
            violations.append(
                f"{path.relative_to(ROOT).as_posix()} constructs {constructor_name} "
                f"as {variable_name} without configure_context_assembler(...)"
            )

    assert not violations, "\n".join(violations)
