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
LONG_LIVED_ANNOTATION = POLICY["long_lived_annotation"]
LONG_LIVED_SOURCES = tuple(POLICY["long_lived_composer_sources"])
LONG_LIVED_FUNCTIONS = set(POLICY["long_lived_composer_functions"])
FORBIDDEN_DATABASE_TYPES = set(POLICY["forbidden_database_types"])
FRAMEWORK_FORBIDDEN_SCOPES = tuple(POLICY["framework_forbidden_scopes"])
UOW_CONSTRUCTOR_FORBIDDEN_SCOPES = tuple(
    POLICY["uow_constructor_forbidden_scopes"]
)
ENGINE_ALLOWED_CONSUMERS = set(POLICY["engine_allowed_consumers"])
ENGINE_ALLOWED_PATHS = tuple(POLICY["engine_allowed_paths"])
FORBIDDEN_RUNTIME_MARKERS = set(POLICY["forbidden_runtime_markers"])
FORBIDDEN_RUNTIME_PATHS = tuple(POLICY["forbidden_runtime_paths"])


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
            if isinstance(node, ast.Call) and _short_name(node.func) == UOW_TYPE:
                violations.append(
                    f"{relative}:{node.lineno}: {UOW_TYPE} construction belongs to composition/persistence, not long-lived execution"
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


def test_arch_run_tx_001_long_lived_composers_have_no_global_uow() -> None:
    found: set[str] = set()
    violations: list[str] = []
    for path in _python_files():
        relative = _relative(path)
        if not _matches(relative, LONG_LIVED_SOURCES):
            continue
        tree = _parse(path)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in LONG_LIVED_FUNCTIONS:
                continue
            found.add(node.name)
            annotation = _short_name(node.returns)
            if annotation != LONG_LIVED_ANNOTATION:
                violations.append(
                    f"{relative}:{node.lineno}: {node.name} must expose a direct {LONG_LIVED_ANNOTATION} boundary"
                )
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _short_name(child.func) == UOW_TYPE:
                    violations.append(
                        f"{relative}:{child.lineno}: long-lived composer {node.name} cannot construct {UOW_TYPE}"
                    )
                if isinstance(child, ast.Name) and child.id == ENGINE_RESOURCE:
                    violations.append(
                        f"{relative}:{child.lineno}: long-lived composer {node.name} cannot consume {ENGINE_RESOURCE}"
                    )
    missing = sorted(LONG_LIVED_FUNCTIONS - found)
    if missing:
        violations.append("missing long-lived composer(s): " + ", ".join(missing))
    assert not violations, "ARCH-RUN-TX-001\n" + "\n".join(violations)


def test_arch_run_tx_002_marker_workflow_architecture_cannot_reappear() -> None:
    violations: list[str] = []
    for path in _python_files():
        relative = _relative(path)
        if _matches(relative, FORBIDDEN_RUNTIME_PATHS):
            violations.append(f"{relative}: marker-based workflow path is forbidden")
        tree = _parse(path)
        for imported, line in _imported_bindings(tree):
            if imported in FORBIDDEN_RUNTIME_MARKERS:
                violations.append(
                    f"{relative}:{line}: marker-based runtime symbol {imported} is forbidden"
                )
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in FORBIDDEN_RUNTIME_MARKERS:
                    violations.append(
                        f"{relative}:{node.lineno}: marker-based runtime definition {node.name} is forbidden"
                    )
            if isinstance(node, ast.Call) and _short_name(node.func) in FORBIDDEN_RUNTIME_MARKERS:
                violations.append(
                    f"{relative}:{node.lineno}: marker-based runtime wrapper is forbidden"
                )
    assert not violations, "ARCH-RUN-TX-002\n" + "\n".join(violations)


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
