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
_CONTEXT_ASSEMBLY = AGENT_ROOT / "application" / "context_assembly.py"
_CONTEXT_ASSEMBLER_CONTRACT = (
    AGENT_ROOT / "application" / "interfaces" / "context_assembler.py"
)
_DEFAULT_ASSEMBLER = AGENT_ROOT / "application" / "default_context_assembler.py"
_DEFAULT_ASSEMBLER_MODULE = "modules.agent.application.default_context_assembler"
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


def test_agent_execution_depends_on_context_assembler_contract_not_default() -> None:
    violations: list[str] = []

    for path in AGENT_EXECUTION.rglob("*.py"):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom):
                if node.module == _DEFAULT_ASSEMBLER_MODULE:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports DefaultContextAssembler"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == _DEFAULT_ASSEMBLER_MODULE:
                        violations.append(
                            f"{path.relative_to(ROOT).as_posix()} imports DefaultContextAssembler"
                        )

    assert not violations, "\n".join(violations)


def test_legacy_assemble_context_is_only_consumed_by_default_adapter() -> None:
    violations: list[str] = []

    for path in AGENT_ROOT.rglob("*.py"):
        if path == _DEFAULT_ASSEMBLER:
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
