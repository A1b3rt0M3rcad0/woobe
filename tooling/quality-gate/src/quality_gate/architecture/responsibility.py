from __future__ import annotations

import ast
from fnmatch import fnmatch
from pathlib import Path
import tomllib
from typing import Iterable

from .policy import ArchitecturePolicy


RawViolation = tuple[str, Path, int, str]


class ResponsibilityPolicyError(ValueError):
    """Raised when a responsibility policy is incomplete or invalid."""


def _matches_prefix(module: str, prefix: str) -> bool:
    prefix = prefix.rstrip(".*")
    return module == prefix or module.startswith(f"{prefix}.")


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ResponsibilityPolicyError(f"{field} must be a list of strings")
    return tuple(value)


def _table(data: dict[str, object], name: str) -> dict[str, object] | None:
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ResponsibilityPolicyError(f"[{name}] must be a table")
    return value


def _rule_id(table: dict[str, object], name: str, default: str) -> str:
    value = table.get("rule_id", default)
    if not isinstance(value, str) or not value:
        raise ResponsibilityPolicyError(f"{name}.rule_id must be a non-empty string")
    return value


def _expand(value: str, policy: ArchitecturePolicy) -> str:
    return value.replace("{package}", policy.package).replace(
        "{module}", policy.module_name
    )


def _expanded_strings(
    table: dict[str, object],
    field: str,
    policy: ArchitecturePolicy,
) -> tuple[str, ...]:
    return tuple(_expand(item, policy) for item in _strings(table.get(field), field=field))


def _expression_name(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expression_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _expression_name(node.value)
    return None


def _imports(tree: ast.Module) -> tuple[tuple[str, int, tuple[str, ...]], ...]:
    values: list[tuple[str, int, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                values.append((alias.name, node.lineno, ()))
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            values.append(
                (
                    node.module,
                    node.lineno,
                    tuple(alias.name for alias in node.names),
                )
            )
    return tuple(values)


def _import_targets(
    module: str,
    aliases: tuple[str, ...],
) -> tuple[str, ...]:
    if not aliases:
        return (module,)
    targets = [module]
    targets.extend(
        f"{module}.{alias}" for alias in aliases if alias != "*"
    )
    return tuple(targets)


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _module_files(root: Path, globs: Iterable[str]) -> tuple[Path, ...]:
    found: set[Path] = set()
    for pattern in globs:
        found.update(
            path
            for path in root.glob(pattern)
            if path.is_file() and path.suffix == ".py"
        )
    return tuple(sorted(found))


def _project_files(project_root: Path, globs: Iterable[str]) -> tuple[Path, ...]:
    found: set[Path] = set()
    for pattern in globs:
        found.update(
            path
            for path in project_root.glob(pattern)
            if path.is_file() and path.suffix == ".py"
        )
    return tuple(sorted(found))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _load_config(
    project_root: Path,
    policy: ArchitecturePolicy,
) -> dict[str, object] | None:
    path = (
        project_root
        / "quality_gate"
        / "architecture"
        / "responsibilities"
        / f"{policy.name}.toml"
    )
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    if not isinstance(data, dict):
        raise ResponsibilityPolicyError(f"{path} must contain TOML tables")
    return data


def _check_layer_surface(
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "layer_surface", "ARCH063")
    root_name = table.get("root")
    if not isinstance(root_name, str) or not root_name:
        raise ResponsibilityPolicyError("layer_surface.root is required")
    allowed = _strings(table.get("allowed"), field="layer_surface.allowed")
    if not allowed:
        raise ResponsibilityPolicyError("layer_surface.allowed cannot be empty")

    surface_root = policy.root / root_name
    if not surface_root.is_dir():
        return ()

    disallowed_roots: dict[str, Path] = {}
    for path in sorted(surface_root.rglob("*.py")):
        relative = _relative(path, policy.root)
        if _matches_any(relative, allowed):
            continue
        parts = Path(relative).parts
        boundary = "/".join(parts[:2]) if len(parts) >= 2 else relative
        disallowed_roots.setdefault(boundary, policy.root / boundary)

    return tuple(
        (
            rule_id,
            path,
            0,
            (
                f"{boundary!r} is outside the declared composition surface; "
                "composition may only contain explicit wiring/resource paths"
            ),
        )
        for boundary, path in sorted(disallowed_roots.items())
    )


def _check_transport_ownership(
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "transport_ownership", "ARCH064")
    imports = _expanded_strings(table, "imports", policy)
    allowed_sources = _strings(
        table.get("allowed_sources"), field="transport_ownership.allowed_sources"
    )
    violations: list[RawViolation] = []
    for path in sorted(policy.root.rglob("*.py")):
        relative = _relative(path, policy.root)
        if _matches_any(relative, allowed_sources):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for module, line, aliases in _imports(tree):
            targets = _import_targets(module, aliases)
            if any(
                _matches_prefix(target, prefix)
                for target in targets
                for prefix in imports
            ):
                violations.append(
                    (
                        rule_id,
                        path,
                        line,
                        (
                            f"transport dependency {module!r} belongs to the "
                            "presentation HTTP boundary"
                        ),
                    )
                )
    return tuple(violations)


def _function_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.arg, ...]:
    return tuple(
        list(node.args.posonlyargs)
        + list(node.args.args)
        + list(node.args.kwonlyargs)
        + ([node.args.vararg] if node.args.vararg is not None else [])
        + ([node.args.kwarg] if node.args.kwarg is not None else [])
    )


def _check_presentation_purity(
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "presentation_purity", "ARCH065")
    sources = _strings(table.get("source"), field="presentation_purity.source")
    forbidden_parameters = set(
        _strings(
            table.get("forbidden_dependency_parameters"),
            field="presentation_purity.forbidden_dependency_parameters",
        )
    )
    forbid_app_state = bool(table.get("forbid_app_state", True))
    violations: list[RawViolation] = []

    for path in _module_files(policy.root, sources):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in _function_args(node):
                    if arg.arg in forbidden_parameters:
                        violations.append(
                            (
                                rule_id,
                                path,
                                arg.lineno,
                                (
                                    f"presentation callable {node.name} cannot receive "
                                    f"infrastructure dependency {arg.arg!r}"
                                ),
                            )
                        )
            if forbid_app_state and isinstance(node, ast.Attribute):
                name = _expression_name(node) or ""
                if ".app.state" in name or name.startswith("app.state"):
                    violations.append(
                        (
                            rule_id,
                            path,
                            node.lineno,
                            (
                                "presentation cannot resolve dependencies from app.state; "
                                "composition must inject handlers/factories explicitly"
                            ),
                        )
                    )
        # Collapse nested Attribute nodes on the same source line.
        by_line: dict[tuple[str, int, str], RawViolation] = {}
        for item in violations:
            by_line[(item[0], item[2], item[3])] = item
        violations = list(by_line.values())
    return tuple(violations)


def _check_import_purity(
    policy: ArchitecturePolicy,
    table: dict[str, object],
    *,
    table_name: str,
    default_rule_id: str,
    message: str,
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, table_name, default_rule_id)
    sources = _strings(table.get("source"), field=f"{table_name}.source")
    forbidden = _expanded_strings(table, "forbidden_imports", policy)
    violations: list[RawViolation] = []
    for path in _module_files(policy.root, sources):
        tree = _parse(path)
        if tree is None:
            continue
        for module, line, aliases in _imports(tree):
            targets = _import_targets(module, aliases)
            if any(
                _matches_prefix(target, prefix)
                for target in targets
                for prefix in forbidden
            ):
                violations.append((rule_id, path, line, message.format(module=module)))
    return tuple(violations)


def _check_runtime_adapter_ownership(
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "runtime_adapter_ownership", "ARCH067")
    allowed_sources = _strings(
        table.get("allowed_sources"),
        field="runtime_adapter_ownership.allowed_sources",
    )
    prefixes = _strings(
        table.get("class_prefixes"),
        field="runtime_adapter_ownership.class_prefixes",
    )
    suffixes = _strings(
        table.get("class_suffixes"),
        field="runtime_adapter_ownership.class_suffixes",
    )
    violations: list[RawViolation] = []
    for path in sorted(policy.root.rglob("*.py")):
        relative = _relative(path, policy.root)
        if _matches_any(relative, allowed_sources):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not (
                any(node.name.startswith(prefix) for prefix in prefixes)
                or any(node.name.endswith(suffix) for suffix in suffixes)
            ):
                continue
            violations.append(
                (
                    rule_id,
                    path,
                    node.lineno,
                    (
                        f"concrete runtime adapter {node.name} belongs to infrastructure, "
                        "not application/presentation/composition"
                    ),
                )
            )
    return tuple(violations)


def _check_composition_behavior(
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "composition_behavior", "ARCH068")
    sources = _strings(table.get("source"), field="composition_behavior.source")
    excludes = _strings(table.get("exclude"), field="composition_behavior.exclude")
    forbidden_methods = set(
        _strings(
            table.get("forbidden_method_calls"),
            field="composition_behavior.forbidden_method_calls",
        )
    )
    forbid_async_functions = bool(table.get("forbid_async_functions", True))
    forbid_async_with = bool(table.get("forbid_async_with", True))
    forbid_yield = bool(table.get("forbid_yield", True))
    violations: list[RawViolation] = []

    for path in _module_files(policy.root, sources):
        relative = _relative(path, policy.root)
        if _matches_any(relative, excludes):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if forbid_async_functions and isinstance(node, ast.AsyncFunctionDef):
                violations.append(
                    (
                        rule_id,
                        path,
                        node.lineno,
                        (
                            f"composition callable {node.name} is async; composition must "
                            "only build the object graph"
                        ),
                    )
                )
            elif forbid_async_with and isinstance(node, ast.AsyncWith):
                violations.append(
                    (
                        rule_id,
                        path,
                        node.lineno,
                        "composition cannot own async resource/runtime lifecycles",
                    )
                )
            elif forbid_yield and isinstance(node, (ast.Yield, ast.YieldFrom)):
                violations.append(
                    (
                        rule_id,
                        path,
                        node.lineno,
                        "composition cannot produce runtime streams",
                    )
                )
            elif isinstance(node, ast.Call):
                called = _expression_name(node.func) or ""
                short = called.rsplit(".", 1)[-1]
                if short in forbidden_methods:
                    violations.append(
                        (
                            rule_id,
                            path,
                            node.lineno,
                            (
                                f"composition cannot execute runtime operation {called}(); "
                                "it may only instantiate/connect dependencies"
                            ),
                        )
                    )
    return tuple(violations)


def _check_responsibility_placement(
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "responsibility_placement", "ARCH069")
    use_case_sources = _strings(
        table.get("use_case_sources"),
        field="responsibility_placement.use_case_sources",
    )
    controller_sources = _strings(
        table.get("controller_sources"),
        field="responsibility_placement.controller_sources",
    )
    sqlalchemy_sources = _strings(
        table.get("sqlalchemy_sources"),
        field="responsibility_placement.sqlalchemy_sources",
    )
    violations: list[RawViolation] = []

    for path in sorted(policy.root.rglob("*.py")):
        relative = _relative(path, policy.root)
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name.endswith("UseCase") and not _matches_any(
                relative, use_case_sources
            ):
                violations.append(
                    (
                        rule_id,
                        path,
                        node.lineno,
                        f"use case {node.name} must live in the application layer",
                    )
                )
            if node.name.endswith("Controller") and not _matches_any(
                relative, controller_sources
            ):
                violations.append(
                    (
                        rule_id,
                        path,
                        node.lineno,
                        f"controller {node.name} must live in the presentation layer",
                    )
                )
            if (
                node.name.startswith("SQLAlchemy")
                or node.name.startswith("SqlAlchemy")
            ) and not _matches_any(relative, sqlalchemy_sources):
                violations.append(
                    (
                        rule_id,
                        path,
                        node.lineno,
                        f"SQLAlchemy implementation {node.name} must live in infrastructure",
                    )
                )
    return tuple(violations)


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check_inbound_composition(
    project_root: Path,
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "inbound_composition", "ARCH070")
    source_root_value = table.get("source_root", "src")
    if not isinstance(source_root_value, str) or not source_root_value:
        raise ResponsibilityPolicyError("inbound_composition.source_root must be a string")
    source_root = project_root / source_root_value
    forbidden = _expanded_strings(table, "forbidden_imports", policy)
    allowed_sources = _strings(
        table.get("allowed_sources"), field="inbound_composition.allowed_sources"
    )
    violations: list[RawViolation] = []

    if not source_root.is_dir():
        return ()
    for path in sorted(source_root.rglob("*.py")):
        if _is_inside(path, policy.root):
            continue
        relative = _relative(path, project_root)
        if _matches_any(relative, allowed_sources):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for module, line, aliases in _imports(tree):
            targets = _import_targets(module, aliases)
            if any(
                _matches_prefix(target, prefix)
                for target in targets
                for prefix in forbidden
            ):
                violations.append(
                    (
                        rule_id,
                        path,
                        line,
                        (
                            f"external source cannot import private composition surface "
                            f"{module!r}; use the bounded-context public API"
                        ),
                    )
                )
    return tuple(violations)


def _check_module_api(
    project_root: Path,
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "module_api", "ARCH071")
    sources = _strings(table.get("source"), field="module_api.source")
    package = table.get("package", "{package}")
    if not isinstance(package, str) or not package:
        raise ResponsibilityPolicyError("module_api.package must be a string")
    package = _expand(package, policy)
    allowed = _expanded_strings(table, "allowed_imports", policy)
    violations: list[RawViolation] = []

    for path in _project_files(project_root, sources):
        tree = _parse(path)
        if tree is None:
            continue
        for module, line, aliases in _imports(tree):
            targets = _import_targets(module, aliases)
            package_targets = [
                target for target in targets if _matches_prefix(target, package)
            ]
            if not package_targets:
                continue
            if all(
                any(_matches_prefix(target, prefix) for prefix in allowed)
                for target in package_targets
            ):
                continue
            violations.append(
                (
                    rule_id,
                    path,
                    line,
                    (
                        f"bootstrap source must access {package!r} through its public "
                        f"entrypoint; import {module!r} exposes module internals"
                    ),
                )
            )
    return tuple(violations)


def _docstring_node_ids(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    owners: list[ast.AST] = [tree]
    owners.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    for owner in owners:
        body = getattr(owner, "body", None)
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def _check_transport_neutral(
    policy: ArchitecturePolicy,
    table: dict[str, object],
) -> tuple[RawViolation, ...]:
    rule_id = _rule_id(table, "transport_neutral", "ARCH072")
    sources = _strings(table.get("source"), field="transport_neutral.source")
    forbidden_imports = _expanded_strings(table, "forbidden_imports", policy)
    markers = _strings(
        table.get("forbidden_string_markers"),
        field="transport_neutral.forbidden_string_markers",
    )
    violations: list[RawViolation] = []

    for path in _module_files(policy.root, sources):
        tree = _parse(path)
        if tree is None:
            continue
        for module, line, aliases in _imports(tree):
            targets = _import_targets(module, aliases)
            if any(
                _matches_prefix(target, prefix)
                for target in targets
                for prefix in forbidden_imports
            ):
                violations.append(
                    (
                        rule_id,
                        path,
                        line,
                        (
                            f"application runtime cannot depend on transport module "
                            f"{module!r}"
                        ),
                    )
                )

        docstrings = _docstring_node_ids(tree)
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                continue
            stripped = node.value.lstrip()
            matched = next(
                (
                    marker
                    for marker in markers
                    if stripped.startswith(marker)
                    or (marker == "text/event-stream" and marker in node.value)
                ),
                None,
            )
            if matched is None:
                continue
            violations.append(
                (
                    rule_id,
                    path,
                    getattr(node, "lineno", 0),
                    (
                        f"application runtime contains transport serialization marker "
                        f"{matched!r}; emit neutral runtime events instead"
                    ),
                )
            )
    return tuple(violations)


def check_responsibility_contracts(
    project_root: Path,
    policy: ArchitecturePolicy,
) -> tuple[RawViolation, ...]:
    data = _load_config(project_root, policy)
    if data is None:
        return ()

    violations: list[RawViolation] = []

    layer_surface = _table(data, "layer_surface")
    if layer_surface is not None:
        violations.extend(_check_layer_surface(policy, layer_surface))

    transport_ownership = _table(data, "transport_ownership")
    if transport_ownership is not None:
        violations.extend(_check_transport_ownership(policy, transport_ownership))

    presentation_purity = _table(data, "presentation_purity")
    if presentation_purity is not None:
        violations.extend(_check_presentation_purity(policy, presentation_purity))

    application_runtime_purity = _table(data, "application_runtime_purity")
    if application_runtime_purity is not None:
        violations.extend(
            _check_import_purity(
                policy,
                application_runtime_purity,
                table_name="application_runtime_purity",
                default_rule_id="ARCH066",
                message=(
                    "application runtime must be framework-neutral; import "
                    "{module!r} belongs to an outer layer"
                ),
            )
        )

    runtime_adapter_ownership = _table(data, "runtime_adapter_ownership")
    if runtime_adapter_ownership is not None:
        violations.extend(
            _check_runtime_adapter_ownership(policy, runtime_adapter_ownership)
        )

    composition_behavior = _table(data, "composition_behavior")
    if composition_behavior is not None:
        violations.extend(_check_composition_behavior(policy, composition_behavior))

    responsibility_placement = _table(data, "responsibility_placement")
    if responsibility_placement is not None:
        violations.extend(
            _check_responsibility_placement(policy, responsibility_placement)
        )

    inbound_composition = _table(data, "inbound_composition")
    if inbound_composition is not None:
        violations.extend(
            _check_inbound_composition(project_root, policy, inbound_composition)
        )

    module_api = _table(data, "module_api")
    if module_api is not None:
        violations.extend(_check_module_api(project_root, policy, module_api))

    transport_neutral = _table(data, "transport_neutral")
    if transport_neutral is not None:
        violations.extend(_check_transport_neutral(policy, transport_neutral))

    return tuple(violations)
