from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from .policy import ArchitecturePolicy, RepositoryContract
from .responsibility import check_responsibility_contracts


RawViolation = tuple[str, Path, int, str]


def _matches_prefix(module: str, prefix: str) -> bool:
    prefix = prefix.rstrip(".*")
    return module == prefix or module.startswith(f"{prefix}.")


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
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _short_name(node: ast.AST | None) -> str | None:
    name = _expression_name(node)
    return name.rsplit(".", 1)[-1] if name else None


def _annotation_names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            name = _expression_name(child)
            if name:
                names.add(name)
                names.add(name.rsplit(".", 1)[-1])
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            names.add(child.value)
    return names


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _imports(tree: ast.Module) -> tuple[tuple[str, int, tuple[str, ...]], ...]:
    values: list[tuple[str, int, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                values.append((alias.name, node.lineno, (alias.asname or alias.name.rsplit(".", 1)[-1],)))
        elif isinstance(node, ast.ImportFrom) and node.module:
            aliases = tuple(alias.asname or alias.name for alias in node.names)
            values.append((node.module, node.lineno, aliases))
    return tuple(values)


def _application_interface_bindings(tree: ast.Module, policy: ArchitecturePolicy) -> set[str]:
    prefix = f"{policy.package}.application.interfaces"
    bindings: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not _matches_prefix(node.module, prefix):
            continue
        bindings.update(alias.asname or alias.name for alias in node.names)
    return bindings


def _module_files(root: Path, globs: Iterable[str]) -> tuple[Path, ...]:
    found: set[Path] = set()
    for pattern in globs:
        found.update(path for path in root.glob(pattern) if path.is_file() and path.suffix == ".py")
    return tuple(sorted(found))


def _project_files(project_root: Path, values: Iterable[str]) -> tuple[Path, ...]:
    found: set[Path] = set()
    for value in values:
        if any(token in value for token in ("*", "?", "[")):
            found.update(path for path in project_root.glob(value) if path.is_file() and path.suffix == ".py")
        else:
            found.add(project_root / value)
    return tuple(sorted(found))


def check_unit_of_work_contract(project_root: Path, policy: ArchitecturePolicy) -> tuple[RawViolation, ...]:
    contract = policy.unit_of_work_contract
    if contract is None:
        return ()
    violations: list[RawViolation] = []

    for deprecated in contract.deprecated_interface_files:
        path = project_root / deprecated
        if path.exists():
            violations.append(("ARCH032", path, 0, "deprecated UnitOfWork contract path must be removed"))

    for path in _project_files(project_root, contract.interface_files):
        if not path.is_file():
            violations.append(("ARCH032", path, 0, "framework-neutral UnitOfWork contract file is required"))
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for module, line, _ in _imports(tree):
            if any(_matches_prefix(module, prefix) for prefix in contract.forbidden_interface_imports):
                violations.append(("ARCH032", path, line, f"UnitOfWork contract cannot import framework/infrastructure module {module!r}"))

    repository_fragments = contract.repository_name_fragments
    for path in _module_files(policy.root, contract.concrete_sources):
        tree = _parse(path)
        if tree is None:
            continue
        if contract.forbid_repository_imports:
            for module, line, aliases in _imports(tree):
                imported_names = (module, *aliases)
                if any(fragment in name for name in imported_names for fragment in repository_fragments):
                    violations.append(("ARCH033", path, line, f"UnitOfWork cannot import or own repository implementation {module!r}"))
        if contract.forbid_repository_properties:
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    is_property = any(_short_name(decorator) == "property" for decorator in item.decorator_list)
                    if is_property and item.name not in contract.allowed_properties:
                        violations.append(("ARCH034", path, item.lineno, f"UnitOfWork property {item.name!r} is forbidden; repositories must be composed explicitly"))
    return tuple(violations)


def _is_concrete_repository(name: str, contract: RepositoryContract) -> bool:
    return name.endswith("Repository") and any(name.startswith(prefix) for prefix in contract.concrete_name_prefixes)


def _repository_classes(tree: ast.Module, contract: RepositoryContract) -> tuple[ast.ClassDef, ...]:
    return tuple(node for node in tree.body if isinstance(node, ast.ClassDef) and _is_concrete_repository(node.name, contract))


def _method_calls(node: ast.AST) -> Iterable[ast.Call]:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            yield child


def _constructor_args(method: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.arg, ...]:
    args = tuple(method.args.posonlyargs) + tuple(method.args.args) + tuple(method.args.kwonlyargs)
    return tuple(arg for arg in args if arg.arg != "self")


def check_repository_contract(project_root: Path, policy: ArchitecturePolicy) -> tuple[RawViolation, ...]:
    contract = policy.repository_contract
    if contract is None:
        return ()
    violations: list[RawViolation] = []

    for path in _module_files(policy.root, contract.interface_sources):
        tree = _parse(path)
        if tree is None:
            continue
        for module, line, _ in _imports(tree):
            if any(_matches_prefix(module, prefix) for prefix in contract.forbidden_interface_imports):
                violations.append(("ARCH035", path, line, f"repository port cannot import framework/infrastructure module {module!r}"))

    concrete_files = list(_module_files(policy.root, contract.concrete_sources))
    concrete_files.extend(_project_files(project_root, contract.external_base_files))
    seen: set[Path] = set()
    for path in concrete_files:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        tree = _parse(path)
        if tree is None:
            continue
        application_interfaces = _application_interface_bindings(tree, policy)

        for repo_class in _repository_classes(tree, contract):
            if contract.require_application_port_base:
                base_names = {_short_name(base) for base in repo_class.bases}
                direct_port_bases = {name for name in base_names if name and name in application_interfaces}
                inherited_repo_bases = {
                    name for name in base_names
                    if name and name.endswith("Repository") and name not in contract.excluded_port_bases
                }
                if not direct_port_bases and not inherited_repo_bases:
                    violations.append(("ARCH037", path, repo_class.lineno, f"{repo_class.name} must implement or extend an application repository port"))

            for method in repo_class.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if method.name == "__init__" and contract.require_uow_constructor:
                    for arg in _constructor_args(method):
                        names = _annotation_names(arg.annotation)
                        forbidden = sorted(names.intersection(contract.forbidden_constructor_types))
                        if forbidden:
                            violations.append(("ARCH039", path, arg.lineno, f"{repo_class.name} constructor cannot receive database framework type(s): {', '.join(forbidden)}"))
                for call in _method_calls(method):
                    target = _expression_name(call.func)
                    short = target.rsplit(".", 1)[-1] if target else None
                    if short in contract.forbidden_transaction_methods:
                        violations.append(("ARCH038", path, call.lineno, f"repository {repo_class.name} cannot control transaction via {short}()"))

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name not in contract.excluded_port_bases:
                continue
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name == "__init__":
                    for arg in _constructor_args(method):
                        names = _annotation_names(arg.annotation)
                        forbidden = sorted(names.intersection(contract.forbidden_constructor_types))
                        if forbidden:
                            violations.append(("ARCH039", path, arg.lineno, f"repository base {node.name} cannot receive database framework type(s): {', '.join(forbidden)}"))
    return tuple(violations)


def _dependency_name(name: str, tokens: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(token.lower() in lowered for token in tokens)


def check_application_contract(project_root: Path, policy: ArchitecturePolicy) -> tuple[RawViolation, ...]:
    del project_root
    contract = policy.application_contract
    if contract is None or not contract.forbid_untyped_dependencies:
        return ()
    violations: list[RawViolation] = []
    for path in _module_files(policy.root, contract.source_globs):
        tree = _parse(path)
        if tree is None:
            continue
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name != "__init__":
                    continue
                positional = list(method.args.posonlyargs) + list(method.args.args)
                defaults_offset = len(positional) - len(method.args.defaults)
                default_by_name: dict[str, ast.AST | None] = {}
                for index, arg in enumerate(positional):
                    default_by_name[arg.arg] = method.args.defaults[index - defaults_offset] if index >= defaults_offset else None
                for arg, default in zip(method.args.kwonlyargs, method.args.kw_defaults):
                    default_by_name[arg.arg] = default
                for arg in _constructor_args(method):
                    if not _dependency_name(arg.arg, contract.dependency_name_tokens):
                        continue
                    if arg.annotation is None:
                        violations.append(("ARCH040", path, arg.lineno, f"application dependency {cls.name}.{arg.arg} must declare an application-owned port type"))
                        continue
                    default = default_by_name.get(arg.arg)
                    if isinstance(default, ast.Constant) and default.value is None:
                        annotation_text = ast.unparse(arg.annotation)
                        if "None" not in annotation_text and "Optional" not in annotation_text:
                            violations.append(("ARCH040", path, arg.lineno, f"optional dependency {cls.name}.{arg.arg} must explicitly include None in its type"))
    return tuple(violations)


def check_semantic_contracts(project_root: Path, policy: ArchitecturePolicy) -> tuple[RawViolation, ...]:
    violations: list[RawViolation] = []
    violations.extend(check_unit_of_work_contract(project_root, policy))
    violations.extend(check_repository_contract(project_root, policy))
    violations.extend(check_application_contract(project_root, policy))
    violations.extend(check_responsibility_contracts(project_root, policy))
    return tuple(violations)
