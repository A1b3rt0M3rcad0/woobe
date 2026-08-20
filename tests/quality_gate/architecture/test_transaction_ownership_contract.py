from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_ROOT = PROJECT_ROOT / "src/modules/agent"
UOW_FILE = AGENT_ROOT / "infra/database/unit_of_work.py"
RESOURCES_FILE = AGENT_ROOT / "composition/resources.py"

PROCESS_RESOURCE_NAMES = {"SETTINGS", "DATABASE_ENGINE", "FILE_STORAGE"}
FORBIDDEN_SESSION_IMPORTS = {
    "AsyncSession",
    "async_sessionmaker",
    "sessionmaker",
    "create_session_factory",
}
FORBIDDEN_DATABASE_FACADE_IMPORTS = {
    "AgentDatabase",
    "AgentDatabaseInput",
    "agent_session_factory",
    "coerce_agent_database",
    "SESSION_FACTORY",
    "AGENT_DATABASE",
}
TRANSACTION_METHODS = {"begin", "commit", "rollback", "close"}


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(path for path in AGENT_ROOT.rglob("*.py") if path.is_file()))


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
                imported.append((alias.asname or alias.name.rsplit(".", 1)[-1], node.lineno))
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


def _is_transaction_target(target: str) -> bool:
    if "." not in target:
        return False
    base, method = target.rsplit(".", 1)
    if method not in TRANSACTION_METHODS:
        return False
    leaf = base.rsplit(".", 1)[-1].lower()
    return leaf in {
        "session",
        "_session",
        "transaction",
        "_transaction",
        "tx",
        "_tx",
    }


def test_arch_uow_001_only_uow_may_create_database_sessions() -> None:
    violations: list[str] = []
    for path in _python_files():
        if path == UOW_FILE:
            continue
        tree = _parse(path)
        relative = path.relative_to(PROJECT_ROOT)
        for imported, line in _imported_names(tree):
            if imported in FORBIDDEN_SESSION_IMPORTS:
                violations.append(f"{relative}:{line}: imports transaction-scoped primitive {imported}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = _name(node.func)
            short = target.rsplit(".", 1)[-1] if target else None
            if short in {"async_sessionmaker", "sessionmaker", "create_session_factory", "open_session"}:
                violations.append(f"{relative}:{node.lineno}: creates/opens a database session via {target}")
    assert not violations, "ARCH-UOW-001\n" + "\n".join(violations)


def test_arch_uow_002_only_uow_may_manage_transaction_lifecycle() -> None:
    violations: list[str] = []
    for path in _python_files():
        if path == UOW_FILE:
            continue
        tree = _parse(path)
        relative = path.relative_to(PROJECT_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = _name(node.func)
            if target and _is_transaction_target(target):
                violations.append(f"{relative}:{node.lineno}: transaction lifecycle call {target}() is UoW-owned")
    assert not violations, "ARCH-UOW-002\n" + "\n".join(violations)


def test_arch_uow_003_runtime_and_composition_cannot_use_database_facades() -> None:
    violations: list[str] = []
    scoped_roots = (AGENT_ROOT / "runtime", AGENT_ROOT / "composition")
    for root in scoped_roots:
        for path in sorted(root.rglob("*.py")):
            tree = _parse(path)
            relative = path.relative_to(PROJECT_ROOT)
            for imported, line in _imported_names(tree):
                if imported in FORBIDDEN_DATABASE_FACADE_IMPORTS:
                    violations.append(f"{relative}:{line}: imports database facade/session factory {imported}")
    assert not violations, "ARCH-UOW-003\n" + "\n".join(violations)


def test_arch_uow_004_process_resources_are_process_scoped_only() -> None:
    tree = _parse(RESOURCES_FILE)
    violations: list[str] = []
    for node in tree.body:
        names: list[tuple[str, int]] = []
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.append((target.id, node.lineno))
        for name, line in names:
            if name.startswith("_") or name in PROCESS_RESOURCE_NAMES:
                continue
            violations.append(f"{RESOURCES_FILE.relative_to(PROJECT_ROOT)}:{line}: process resource {name} is not allowed")
    assert not violations, "ARCH-UOW-004\n" + "\n".join(violations)


def test_arch_uow_005_agent_uow_accepts_engine_only() -> None:
    tree = _parse(UOW_FILE)
    violations: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "AgentUnitOfWork":
            continue
        init = next(
            (
                item
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__"
            ),
            None,
        )
        assert init is not None, "AgentUnitOfWork must define __init__"
        args = [arg for arg in (*init.args.posonlyargs, *init.args.args, *init.args.kwonlyargs) if arg.arg != "self"]
        if len(args) != 1:
            violations.append(f"{UOW_FILE.relative_to(PROJECT_ROOT)}:{init.lineno}: AgentUnitOfWork must accept exactly one AsyncEngine")
            continue
        arg = args[0]
        names = _annotation_names(arg.annotation)
        if "AsyncEngine" not in names or names.intersection({"AgentDatabase", "async_sessionmaker", "AsyncSession"}):
            violations.append(
                f"{UOW_FILE.relative_to(PROJECT_ROOT)}:{arg.lineno}: AgentUnitOfWork constructor must accept AsyncEngine only; got {ast.unparse(arg.annotation) if arg.annotation else '<untyped>'}"
            )
    assert not violations, "ARCH-UOW-005\n" + "\n".join(violations)
