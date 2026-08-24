from __future__ import annotations

import ast
from fnmatch import fnmatch
from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[3]
POLICY_FILE = (
    PROJECT_ROOT
    / "quality_gate/architecture/policies/contracts/agent_runtime_transaction_boundaries.toml"
)
with POLICY_FILE.open("rb") as stream:
    POLICY = tomllib.load(stream)["runtime_transaction_boundaries"]

AGENT_ROOT = PROJECT_ROOT / POLICY["module_root"]
RESOURCES_FILE = PROJECT_ROOT / POLICY["resources_file"]
UOW_TYPE = POLICY["uow_type"]
ENGINE_RESOURCE = POLICY["engine_resource"]
WORKFLOW_HANDLER = POLICY["workflow_handler"]
WORKFLOW_SOURCES = tuple(POLICY["workflow_sources"])
WORKFLOW_FUNCTIONS = set(POLICY["workflow_functions"])
FORBIDDEN_DATABASE_TYPES = set(POLICY["forbidden_database_types"])
FRAMEWORK_FORBIDDEN_SCOPES = tuple(POLICY["framework_forbidden_scopes"])
UOW_CONSTRUCTOR_FORBIDDEN_SCOPES = tuple(
    POLICY["uow_constructor_forbidden_scopes"]
)
ENGINE_ALLOWED_CONSUMERS = set(POLICY["engine_allowed_consumers"])
ENGINE_ALLOWED_PATHS = tuple(POLICY["engine_allowed_paths"])


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _relative(path: Path) -> str:
    return path.relative_to(AGENT_ROOT).as_posix()


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


def _in_scope(relative: str, scopes: tuple[str, ...]) -> bool:
    return any(relative == scope or relative.startswith(f"{scope}/") for scope in scopes)


def _matches(relative: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(relative, pattern) for pattern in patterns)


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(path for path in AGENT_ROOT.rglob("*.py") if path.is_file()))


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
    nodes = list(call.args)
    nodes.extend(keyword.value for keyword in call.keywords)
    return any(
        isinstance(child, ast.Name) and child.id == name
        for node in nodes
        for child in ast.walk(node)
    )


def test_arch_uow_006_database_framework_resources_do_not_escape_to_runtime() -> None:
    violations: list[str] = []
    for path in _python_files():
        relative = _relative(path)
        if not _in_scope(relative, FRAMEWORK_FORBIDDEN_SCOPES):
            continue
        tree = _parse(path)
        for imported, line in _imported_bindings(tree):
            if imported in FORBIDDEN_DATABASE_TYPES:
                violations.append(
                    f"{relative}:{line}: database framework type {imported} escaped into runtime/application boundary"
                )
    assert not violations, "ARCH-UOW-006\n" + "\n".join(violations)


def test_arch_uow_007_runtime_cannot_construct_unit_of_work() -> None:
    violations: list[str] = []
    for path in _python_files():
        relative = _relative(path)
        if not _in_scope(relative, UOW_CONSTRUCTOR_FORBIDDEN_SCOPES):
            continue
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _short_name(node.func) == UOW_TYPE:
                violations.append(
                    f"{relative}:{node.lineno}: {UOW_TYPE} construction belongs to composition, not runtime"
                )
    assert not violations, "ARCH-UOW-007\n" + "\n".join(violations)


def test_arch_uow_008_engine_is_consumed_only_by_uow_construction() -> None:
    violations: list[str] = []
    for path in _python_files():
        if path == RESOURCES_FILE:
            continue
        relative = _relative(path)
        tree = _parse(path)
        imports_engine = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (alias.asname or alias.name) == ENGINE_RESOURCE:
                        imports_engine = True
            if not isinstance(node, ast.Call) or not _call_contains_name(
                node,
                ENGINE_RESOURCE,
            ):
                continue
            consumer = _short_name(node.func)
            if consumer not in ENGINE_ALLOWED_CONSUMERS:
                violations.append(
                    f"{relative}:{node.lineno}: {ENGINE_RESOURCE} cannot be passed to {consumer or '<unknown>'}; it may only construct {UOW_TYPE}"
                )
        if imports_engine and not _matches(relative, ENGINE_ALLOWED_PATHS):
            violations.append(
                f"{relative}: imports {ENGINE_RESOURCE} outside the explicit UoW construction surface"
            )
    assert not violations, "ARCH-UOW-008\n" + "\n".join(violations)


def test_arch_workflow_001_long_lived_composers_have_no_global_uow() -> None:
    found: set[str] = set()
    violations: list[str] = []
    for path in _python_files():
        relative = _relative(path)
        if not _matches(relative, WORKFLOW_SOURCES):
            continue
        tree = _parse(path)
        imported = {name for name, _ in _imported_bindings(tree)}
        leaked = sorted(imported.intersection(FORBIDDEN_DATABASE_TYPES | {ENGINE_RESOURCE}))
        if leaked:
            violations.append(
                f"{relative}: workflow imports database resource/type(s): {', '.join(leaked)}"
            )
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in WORKFLOW_FUNCTIONS:
                continue
            found.add(node.name)
            annotation = _short_name(node.returns)
            if annotation != WORKFLOW_HANDLER:
                violations.append(
                    f"{relative}:{node.lineno}: {node.name} must return {WORKFLOW_HANDLER}"
                )
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _short_name(child.func) == UOW_TYPE:
                    violations.append(
                        f"{relative}:{child.lineno}: workflow {node.name} cannot construct {UOW_TYPE}"
                    )
            returns = [child for child in ast.walk(node) if isinstance(child, ast.Return)]
            if not any(
                isinstance(item.value, ast.Call)
                and _short_name(item.value.func) == WORKFLOW_HANDLER
                for item in returns
            ):
                violations.append(
                    f"{relative}:{node.lineno}: {node.name} must terminate in {WORKFLOW_HANDLER}"
                )

    missing = sorted(WORKFLOW_FUNCTIONS - found)
    if missing:
        violations.append("missing workflow composer(s): " + ", ".join(missing))
    assert not violations, "ARCH-WORKFLOW-001\n" + "\n".join(violations)


def test_arch_uow_008_detects_engine_propagation_fixture() -> None:
    source = "handler = build_handler(DATABASE_ENGINE, SETTINGS)\n"
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    violations = [
        node
        for node in calls
        if _call_contains_name(node, ENGINE_RESOURCE)
        and _short_name(node.func) not in ENGINE_ALLOWED_CONSUMERS
    ]
    assert len(violations) == 1


def test_arch_uow_007_detects_nested_uow_fixture() -> None:
    source = "async with AgentUnitOfWork(self._engine) as uow:\n    pass\n"
    tree = ast.parse(source)
    violations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _short_name(node.func) == UOW_TYPE
    ]
    assert len(violations) == 1
