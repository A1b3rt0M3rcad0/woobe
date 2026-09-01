from __future__ import annotations

import ast
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
import tomllib

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_DIR = (
    PROJECT_ROOT
    / "tooling/quality-gate/src/quality_gate/architecture/policies/contracts"
)


@dataclass(frozen=True)
class RuntimeTransactionContract:
    name: str
    module_root: Path
    resources_file: Path
    uow_type: str
    engine_resource: str
    long_lived_annotation: str
    long_lived_composer_sources: tuple[str, ...]
    long_lived_composer_functions: frozenset[str]
    forbidden_database_types: frozenset[str]
    framework_forbidden_scopes: tuple[str, ...]
    uow_constructor_forbidden_scopes: tuple[str, ...]
    engine_allowed_consumers: frozenset[str]
    engine_allowed_paths: tuple[str, ...]
    forbidden_runtime_markers: frozenset[str]
    forbidden_runtime_paths: tuple[str, ...]


def _load_contracts() -> tuple[RuntimeTransactionContract, ...]:
    contracts: list[RuntimeTransactionContract] = []
    for path in sorted(CONTRACT_DIR.glob("*_runtime_transaction_boundaries.toml")):
        with path.open("rb") as stream:
            policy = tomllib.load(stream)["runtime_transaction_boundaries"]
        contracts.append(
            RuntimeTransactionContract(
                name=str(policy.get("module") or path.stem.removesuffix("_runtime_transaction_boundaries")),
                module_root=PROJECT_ROOT / policy["module_root"],
                resources_file=PROJECT_ROOT / policy["resources_file"],
                uow_type=policy["uow_type"],
                engine_resource=policy["engine_resource"],
                long_lived_annotation=policy["long_lived_annotation"],
                long_lived_composer_sources=tuple(policy["long_lived_composer_sources"]),
                long_lived_composer_functions=frozenset(policy["long_lived_composer_functions"]),
                forbidden_database_types=frozenset(policy["forbidden_database_types"]),
                framework_forbidden_scopes=tuple(policy["framework_forbidden_scopes"]),
                uow_constructor_forbidden_scopes=tuple(policy["uow_constructor_forbidden_scopes"]),
                engine_allowed_consumers=frozenset(policy["engine_allowed_consumers"]),
                engine_allowed_paths=tuple(policy["engine_allowed_paths"]),
                forbidden_runtime_markers=frozenset(policy["forbidden_runtime_markers"]),
                forbidden_runtime_paths=tuple(policy["forbidden_runtime_paths"]),
            )
        )
    assert contracts, "no runtime transaction boundary contracts found"
    return tuple(contracts)


CONTRACTS = _load_contracts()


def _id(contract: RuntimeTransactionContract) -> str:
    return contract.name


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _name(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _name(node.value)
    return None


def _short_name(node: ast.AST | None) -> str | None:
    value = _name(node)
    return value.rsplit(".", 1)[-1] if value else None


def _relative(path: Path, contract: RuntimeTransactionContract) -> str:
    return path.relative_to(contract.module_root).as_posix()


def _matches(relative: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(relative, pattern) for pattern in patterns)


def _in_scope(relative: str, scopes: tuple[str, ...]) -> bool:
    return any(relative == scope or relative.startswith(f"{scope}/") for scope in scopes)


def _python_files(contract: RuntimeTransactionContract) -> tuple[Path, ...]:
    assert contract.module_root.is_dir(), f"{contract.name}: missing module root"
    return tuple(sorted(contract.module_root.rglob("*.py")))


def _imported_bindings(tree: ast.Module) -> tuple[tuple[str, int], ...]:
    values: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                values.append((alias.asname or alias.name.rsplit(".", 1)[-1], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                values.append((alias.asname or alias.name, node.lineno))
    return tuple(values)


def _call_contains_name(call: ast.Call, name: str) -> bool:
    nodes = [*call.args, *(keyword.value for keyword in call.keywords)]
    return any(
        isinstance(child, ast.Name) and child.id == name
        for node in nodes
        for child in ast.walk(node)
    )


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_006_database_framework_resources_do_not_escape_to_runtime(
    contract: RuntimeTransactionContract,
) -> None:
    violations: list[str] = []
    for path in _python_files(contract):
        relative = _relative(path, contract)
        if not _in_scope(relative, contract.framework_forbidden_scopes):
            continue
        for imported, line in _imported_bindings(_parse(path)):
            if imported in contract.forbidden_database_types:
                violations.append(
                    f"{relative}:{line}: database framework type {imported} escaped "
                    "into a long-lived/application boundary"
                )
    assert not violations, f"ARCH-UOW-006 [{contract.name}]\n" + "\n".join(violations)


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_007_runtime_cannot_construct_unit_of_work(
    contract: RuntimeTransactionContract,
) -> None:
    violations: list[str] = []
    for path in _python_files(contract):
        relative = _relative(path, contract)
        if not _in_scope(relative, contract.uow_constructor_forbidden_scopes):
            continue
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Call) and _short_name(node.func) == contract.uow_type:
                violations.append(
                    f"{relative}:{node.lineno}: {contract.uow_type} construction belongs "
                    "to short-lived composition/persistence boundaries"
                )
    assert not violations, f"ARCH-UOW-007 [{contract.name}]\n" + "\n".join(violations)


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_008_engine_is_consumed_only_by_uow_construction(
    contract: RuntimeTransactionContract,
) -> None:
    violations: list[str] = []
    for path in _python_files(contract):
        if path == contract.resources_file:
            continue
        relative = _relative(path, contract)
        tree = _parse(path)
        imports_engine = any(
            isinstance(node, ast.ImportFrom)
            and any((alias.asname or alias.name) == contract.engine_resource for alias in node.names)
            for node in ast.walk(tree)
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _call_contains_name(node, contract.engine_resource):
                continue
            consumer = _short_name(node.func)
            if consumer not in contract.engine_allowed_consumers:
                violations.append(
                    f"{relative}:{node.lineno}: {contract.engine_resource} cannot be passed "
                    f"to {consumer or '<unknown>'}; it may only construct {contract.uow_type}"
                )
        if imports_engine and not _matches(relative, contract.engine_allowed_paths):
            violations.append(
                f"{relative}: imports {contract.engine_resource} outside the explicit "
                "UoW construction surface"
            )
    assert not violations, f"ARCH-UOW-008 [{contract.name}]\n" + "\n".join(violations)


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_run_tx_001_long_lived_composers_have_no_global_uow(
    contract: RuntimeTransactionContract,
) -> None:
    if not contract.long_lived_composer_functions:
        return
    found: set[str] = set()
    violations: list[str] = []
    for path in _python_files(contract):
        relative = _relative(path, contract)
        if not _matches(relative, contract.long_lived_composer_sources):
            continue
        for node in _parse(path).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in contract.long_lived_composer_functions:
                continue
            found.add(node.name)
            if _short_name(node.returns) != contract.long_lived_annotation:
                violations.append(
                    f"{relative}:{node.lineno}: {node.name} must expose a direct "
                    f"{contract.long_lived_annotation} boundary"
                )
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _short_name(child.func) == contract.uow_type:
                    violations.append(
                        f"{relative}:{child.lineno}: long-lived composer {node.name} "
                        f"cannot construct {contract.uow_type}"
                    )
                if isinstance(child, ast.Name) and child.id == contract.engine_resource:
                    violations.append(
                        f"{relative}:{child.lineno}: long-lived composer {node.name} "
                        f"cannot consume {contract.engine_resource}"
                    )
    missing = sorted(contract.long_lived_composer_functions - found)
    if missing:
        violations.append("missing long-lived composer(s): " + ", ".join(missing))
    assert not violations, f"ARCH-RUN-TX-001 [{contract.name}]\n" + "\n".join(violations)


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_run_tx_002_marker_workflow_architecture_cannot_reappear(
    contract: RuntimeTransactionContract,
) -> None:
    violations: list[str] = []
    for path in _python_files(contract):
        relative = _relative(path, contract)
        if _matches(relative, contract.forbidden_runtime_paths):
            violations.append(f"{relative}: marker-based workflow path is forbidden")
        tree = _parse(path)
        for imported, line in _imported_bindings(tree):
            if imported in contract.forbidden_runtime_markers:
                violations.append(
                    f"{relative}:{line}: marker-based runtime symbol {imported} is forbidden"
                )
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in contract.forbidden_runtime_markers:
                    violations.append(
                        f"{relative}:{node.lineno}: marker-based runtime definition "
                        f"{node.name} is forbidden"
                    )
            if isinstance(node, ast.Call) and _short_name(node.func) in contract.forbidden_runtime_markers:
                violations.append(
                    f"{relative}:{node.lineno}: marker-based runtime wrapper is forbidden"
                )
    assert not violations, f"ARCH-RUN-TX-002 [{contract.name}]\n" + "\n".join(violations)
