from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import tomllib

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_DIR = (
    PROJECT_ROOT
    / "tooling/quality-gate/src/quality_gate/architecture/policies/contracts"
)


@dataclass(frozen=True)
class TransactionOwnershipContract:
    name: str
    module_root: Path
    uow_file: Path
    resources_file: Path
    process_resources: frozenset[str]
    forbidden_database_facades: frozenset[str]
    forbidden_session_creators: frozenset[str]
    transaction_methods: frozenset[str]
    transaction_target_names: frozenset[str]
    facade_forbidden_scopes: tuple[str, ...]
    uow_type: str
    uow_engine_type: str
    forbidden_uow_constructor_types: frozenset[str]


def _load_contracts() -> tuple[TransactionOwnershipContract, ...]:
    contracts: list[TransactionOwnershipContract] = []
    for path in sorted(CONTRACT_DIR.glob("*_transaction_ownership.toml")):
        with path.open("rb") as stream:
            policy = tomllib.load(stream)["transaction_ownership"]
        contracts.append(
            TransactionOwnershipContract(
                name=str(policy.get("module") or path.stem.removesuffix("_transaction_ownership")),
                module_root=PROJECT_ROOT / policy["module_root"],
                uow_file=PROJECT_ROOT / policy["uow_file"],
                resources_file=PROJECT_ROOT / policy["resources_file"],
                process_resources=frozenset(policy["process_resources"]),
                forbidden_database_facades=frozenset(policy["forbidden_database_facades"]),
                forbidden_session_creators=frozenset(policy["forbidden_session_creators"]),
                transaction_methods=frozenset(policy["transaction_methods"]),
                transaction_target_names=frozenset(policy["transaction_target_names"]),
                facade_forbidden_scopes=tuple(policy["facade_forbidden_scopes"]),
                uow_type=policy["uow_type"],
                uow_engine_type=policy["uow_engine_type"],
                forbidden_uow_constructor_types=frozenset(
                    policy["forbidden_uow_constructor_types"]
                ),
            )
        )
    assert contracts, "no transaction ownership contracts found"
    return tuple(contracts)


CONTRACTS = _load_contracts()


def _id(contract: TransactionOwnershipContract) -> str:
    return contract.name


def _python_files(contract: TransactionOwnershipContract) -> tuple[Path, ...]:
    assert contract.module_root.is_dir(), (
        f"{contract.name}: module root is missing: "
        f"{contract.module_root.relative_to(PROJECT_ROOT)}"
    )
    return tuple(
        sorted(path for path in contract.module_root.rglob("*.py") if path.is_file())
    )


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


def _imported_names(tree: ast.Module) -> tuple[tuple[str, int], ...]:
    imported: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append(
                    (alias.asname or alias.name.rsplit(".", 1)[-1], node.lineno)
                )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.append((alias.asname or alias.name, node.lineno))
    return tuple(imported)


def _annotation_names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    values: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            values.add(child.id)
        elif isinstance(child, ast.Attribute):
            value = _name(child)
            if value:
                values.add(value)
                values.add(value.rsplit(".", 1)[-1])
    return values


def _is_transaction_target(
    target: str,
    contract: TransactionOwnershipContract,
) -> bool:
    if "." not in target:
        return False
    base, method = target.rsplit(".", 1)
    if method not in contract.transaction_methods:
        return False
    leaf = base.rsplit(".", 1)[-1].lower()
    return leaf in contract.transaction_target_names


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_001_only_uow_may_create_or_open_database_sessions(
    contract: TransactionOwnershipContract,
) -> None:
    violations: list[str] = []
    for path in _python_files(contract):
        if path == contract.uow_file:
            continue
        tree = _parse(path)
        relative = path.relative_to(PROJECT_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = _name(node.func)
            short = target.rsplit(".", 1)[-1] if target else None
            if short in contract.forbidden_session_creators:
                violations.append(
                    f"{relative}:{node.lineno}: creates/opens a database session via {target}"
                )
    assert not violations, f"ARCH-UOW-001 [{contract.name}]\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_002_only_uow_may_manage_transaction_lifecycle(
    contract: TransactionOwnershipContract,
) -> None:
    violations: list[str] = []
    for path in _python_files(contract):
        if path == contract.uow_file:
            continue
        tree = _parse(path)
        relative = path.relative_to(PROJECT_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = _name(node.func)
            if target and _is_transaction_target(target, contract):
                violations.append(
                    f"{relative}:{node.lineno}: transaction lifecycle call "
                    f"{target}() is UoW-owned"
                )
    assert not violations, f"ARCH-UOW-002 [{contract.name}]\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_003_application_presentation_and_composition_cannot_use_database_facades(
    contract: TransactionOwnershipContract,
) -> None:
    violations: list[str] = []
    scoped_roots = tuple(
        contract.module_root / scope for scope in contract.facade_forbidden_scopes
    )
    for root in scoped_roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            tree = _parse(path)
            relative = path.relative_to(PROJECT_ROOT)
            for imported, line in _imported_names(tree):
                if imported in contract.forbidden_database_facades:
                    violations.append(
                        f"{relative}:{line}: imports database facade/session factory "
                        f"{imported}"
                    )
    assert not violations, f"ARCH-UOW-003 [{contract.name}]\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_004_process_resources_are_declared_explicitly(
    contract: TransactionOwnershipContract,
) -> None:
    assert contract.resources_file.is_file(), (
        f"ARCH-UOW-004 [{contract.name}]\n"
        f"missing composition resources file: "
        f"{contract.resources_file.relative_to(PROJECT_ROOT)}"
    )
    tree = _parse(contract.resources_file)
    violations: list[str] = []
    for node in tree.body:
        names: list[tuple[str, int]] = []
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.append((target.id, node.lineno))
        for name, line in names:
            if name.startswith("_") or name in contract.process_resources:
                continue
            violations.append(
                f"{contract.resources_file.relative_to(PROJECT_ROOT)}:{line}: "
                f"process resource {name} is not declared by the module contract"
            )
    assert not violations, f"ARCH-UOW-004 [{contract.name}]\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize("contract", CONTRACTS, ids=_id)
def test_arch_uow_005_uow_accepts_engine_only(
    contract: TransactionOwnershipContract,
) -> None:
    assert contract.uow_file.is_file(), (
        f"ARCH-UOW-005 [{contract.name}]\n"
        f"missing UnitOfWork file: {contract.uow_file.relative_to(PROJECT_ROOT)}"
    )
    tree = _parse(contract.uow_file)
    violations: list[str] = []
    found = False
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != contract.uow_type:
            continue
        found = True
        init = next(
            (
                item
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == "__init__"
            ),
            None,
        )
        assert init is not None, f"{contract.uow_type} must define __init__"
        args = [
            arg
            for arg in (*init.args.posonlyargs, *init.args.args, *init.args.kwonlyargs)
            if arg.arg != "self"
        ]
        if len(args) != 1:
            violations.append(
                f"{contract.uow_file.relative_to(PROJECT_ROOT)}:{init.lineno}: "
                f"{contract.uow_type} must accept exactly one "
                f"{contract.uow_engine_type}"
            )
            continue
        arg = args[0]
        names = _annotation_names(arg.annotation)
        if (
            contract.uow_engine_type not in names
            or names.intersection(contract.forbidden_uow_constructor_types)
        ):
            annotation = ast.unparse(arg.annotation) if arg.annotation else "<untyped>"
            violations.append(
                f"{contract.uow_file.relative_to(PROJECT_ROOT)}:{arg.lineno}: "
                f"{contract.uow_type} constructor must accept "
                f"{contract.uow_engine_type} only; got {annotation}"
            )
    if not found:
        violations.append(
            f"{contract.uow_file.relative_to(PROJECT_ROOT)}: "
            f"missing {contract.uow_type}"
        )
    assert not violations, f"ARCH-UOW-005 [{contract.name}]\n" + "\n".join(
        violations
    )
