from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
import sys
from typing import Iterable

from .graph import strongly_connected_components
from .policy import ArchitecturePolicy, ComposerContract, ImportRule, load_policies
from .semantic import check_semantic_contracts


@dataclass(frozen=True, slots=True, order=True)
class Violation:
    rule_id: str
    file: str
    line: int
    message: str


@dataclass(frozen=True, slots=True)
class QualityGateResult:
    module: str
    violations: tuple[Violation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations


@dataclass(frozen=True, slots=True)
class ImportReference:
    module: str
    line: int
    wildcard: bool = False


def _matches_prefix(module: str, prefix: str) -> bool:
    prefix = prefix.rstrip(".*")
    return module == prefix or module.startswith(f"{prefix}.")


def _module_name_for_file(policy: ArchitecturePolicy, file: Path) -> str:
    relative = file.relative_to(policy.root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    suffix = ".".join(parts)
    return policy.package if not suffix else f"{policy.package}.{suffix}"


def _resolve_relative_import(policy: ArchitecturePolicy, file: Path, node: ast.ImportFrom) -> str:
    current = _module_name_for_file(policy, file)
    current_parts = current.split(".")
    if file.name != "__init__.py":
        current_parts = current_parts[:-1]
    ascend = max(node.level - 1, 0)
    if ascend:
        current_parts = current_parts[:-ascend]
    if node.module:
        current_parts.extend(node.module.split("."))
    return ".".join(current_parts)


def _extract_imports(policy: ArchitecturePolicy, file: Path, tree: ast.AST) -> tuple[ImportReference, ...]:
    imports: list[ImportReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(ImportReference(alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_relative_import(policy, file, node) if node.level else (node.module or "")
            if module:
                imports.append(ImportReference(module=module, line=node.lineno, wildcard=any(alias.name == "*" for alias in node.names)))
    return tuple(imports)


def _is_dynamic_import(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id == "__import__"
    if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
        return isinstance(node.func.value, ast.Name) and node.func.value.id == "importlib"
    return False


def _cross_module_target(policy: ArchitecturePolicy, imported: str) -> str | None:
    parts = imported.split(".")
    if len(parts) < 2 or parts[0] != "modules":
        return None
    return parts[1] if parts[1] != policy.module_name else None


def _is_governed_internal(imported: str) -> bool:
    return imported == "shared" or imported.startswith("shared.") or imported.startswith("modules.")


def _rule_violation(rule: ImportRule, imported: str) -> str | None:
    for prefix in rule.deny_prefixes:
        if _matches_prefix(imported, prefix):
            return f"{rule.description}: import of {imported!r} is forbidden"
    if rule.enforce_internal_allowlist and _is_governed_internal(imported):
        if not any(_matches_prefix(imported, prefix) for prefix in rule.allow_prefixes):
            return f"{rule.description}: import of {imported!r} is outside the allowed dependency surface"
    return None


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


def _short_name(name: str | None) -> str | None:
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


class _ComposerBodyInspector(ast.NodeVisitor):
    CONTROL_FLOW = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Match,
        ast.Await,
        ast.Yield,
        ast.YieldFrom,
    )

    def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.root = root
        self.returns: list[ast.Return] = []
        self.async_with: list[ast.AsyncWith] = []
        self.awaits: list[ast.Await] = []
        self.assignments: list[tuple[str, ast.AST, int]] = []
        self.control_flow: list[ast.AST] = []
        self.nested_definitions: list[ast.AST] = []
        self.calls: list[ast.Call] = []
        self.attributes: list[ast.Attribute] = []

    def inspect(self) -> "_ComposerBodyInspector":
        for statement in self.root.body:
            self.visit(statement)
        return self

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, self.CONTROL_FLOW):
            self.control_flow.append(node)
        super().generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.returns.append(node)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.async_with.append(node)
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:
        self.awaits.append(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.attributes.append(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assignments.append((target.id, node.value, node.lineno))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            self.assignments.append((node.target.id, node.value, node.lineno))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)
        else:
            self.nested_definitions.append(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)
        else:
            self.nested_definitions.append(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.nested_definitions.append(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.nested_definitions.append(node)


def _call_target(node: ast.AST | None) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    return _short_name(_expression_name(node.func))


def _uow_call(node: ast.AST | None, contract: ComposerContract) -> bool:
    target = _call_target(node)
    return target in set(contract.uow_types).union(contract.uow_factory_functions)


def _function_args(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.arg, ...]:
    args = list(function.args.posonlyargs) + list(function.args.args) + list(function.args.kwonlyargs)
    if function.args.vararg is not None:
        args.append(function.args.vararg)
    if function.args.kwarg is not None:
        args.append(function.args.kwarg)
    return tuple(arg for arg in args if arg.arg not in {"self", "cls"})


def _is_repository_call(call: ast.Call, contract: ComposerContract) -> bool:
    target = _short_name(_expression_name(call.func)) or ""
    return any(target.endswith(suffix) for suffix in contract.repository_suffixes)


def _parameter_is_dependency(arg: ast.arg, contract: ComposerContract) -> bool:
    candidates = {arg.arg.lower()}
    candidates.update(item.lower() for item in _annotation_names(arg.annotation))
    return any(token.lower() in candidate for candidate in candidates for token in contract.dependency_parameter_tokens)


def _module_level_composer_violations(contract: ComposerContract, tree: ast.Module) -> list[tuple[str, int, str]]:
    violations: list[tuple[str, int, str]] = []
    transient_suffixes = contract.transient_suffixes
    forbidden_module_calls = set(contract.forbidden_module_level_calls)
    for statement in tree.body:
        value: ast.AST | None = None
        target_name = "module value"
        if isinstance(statement, ast.Assign):
            value = statement.value
            names = [target.id for target in statement.targets if isinstance(target, ast.Name)]
            if names:
                target_name = ", ".join(names)
        elif isinstance(statement, ast.AnnAssign):
            value = statement.value
            if isinstance(statement.target, ast.Name):
                target_name = statement.target.id
        if not isinstance(value, ast.Call):
            continue
        called = _call_target(value) or ""
        if contract.forbid_module_level_transients and any(called.endswith(suffix) for suffix in transient_suffixes):
            violations.append(("ARCH054", statement.lineno, f"composer modules cannot keep transient {called} instances at module scope ({target_name})"))
        if called in forbidden_module_calls:
            violations.append(("ARCH061", statement.lineno, f"process resource {called}() must be created in a composition resource module, not in a composer module"))
    return violations


def _composer_violations(contract: ComposerContract, relative: str, tree: ast.Module) -> tuple[tuple[str, int, str], ...]:
    if not any(fnmatch(relative, pattern) for pattern in contract.source_globs):
        return ()

    violations = _module_level_composer_violations(contract, tree)
    for function in tree.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if function.name.startswith("_") or not function.name.endswith(contract.function_suffix):
            continue

        is_long_lived = function.name in set(contract.long_lived_functions)
        is_stream = function.name.endswith(contract.streaming_suffix)
        expected_handler = (
            contract.long_lived_handler
            if is_long_lived
            else contract.streaming_handler if is_stream else contract.regular_handler
        )
        annotation = _short_name(_expression_name(function.returns))
        if annotation != expected_handler:
            rule = "ARCH020" if is_long_lived else "ARCH023" if is_stream else "ARCH021"
            violations.append((rule, function.lineno, f"{function.name} must declare return type {expected_handler}"))

        function_args = _function_args(function)
        if contract.require_zero_arguments:
            for arg in function_args:
                rule = "ARCH051" if _parameter_is_dependency(arg, contract) else "ARCH062"
                if rule == "ARCH051":
                    message = f"{function.name} is a composition root and cannot receive dependency {arg.arg!r}; resolve it inside composition"
                else:
                    message = f"{function.name} must be a zero-argument factory; operation data belongs to the request/DTO, not the composer signature"
                violations.append((rule, arg.lineno, message))
        else:
            for arg in function_args:
                if arg.arg in contract.forbidden_parameter_names:
                    violations.append(("ARCH030", arg.lineno, f"{function.name} cannot receive framework-shaped parameter {arg.arg!r}"))
                forbidden_types = _annotation_names(arg.annotation).intersection(contract.forbidden_parameter_types)
                if forbidden_types:
                    violations.append(("ARCH030", arg.lineno, f"{function.name} cannot expose framework type(s) in its signature: {', '.join(sorted(forbidden_types))}"))

        inspector = _ComposerBodyInspector(function).inspect()
        if isinstance(function, ast.AsyncFunctionDef) or inspector.awaits:
            violations.append(("ARCH022", function.lineno, f"{function.name} must compose dependencies without executing async work"))

        if contract.forbid_control_flow:
            for node in inspector.control_flow:
                if isinstance(node, ast.Await):
                    continue
                violations.append(("ARCH027", getattr(node, "lineno", function.lineno), f"{function.name} must be pure wiring; {type(node).__name__} is forbidden"))

        if contract.forbid_nested_definitions:
            for node in inspector.nested_definitions:
                violations.append(("ARCH028", getattr(node, "lineno", function.lineno), f"{function.name} cannot define nested runtime helpers"))

        for call in inspector.calls:
            target = _expression_name(call.func) or ""
            if any(target == forbidden or target.endswith(f".{forbidden}") for forbidden in contract.forbidden_calls):
                violations.append(("ARCH031", call.lineno, f"{function.name} cannot construct or resolve operational configuration via {target}()"))

        if contract.forbid_composed_dependency_calls:
            composed_names = {name for name, value, _ in inspector.assignments if isinstance(value, ast.Call)}
            for call in inspector.calls:
                if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
                    continue
                owner = call.func.value.id
                if owner not in composed_names:
                    continue
                violations.append(("ARCH059", call.lineno, f"{function.name} cannot execute composed dependency {owner}.{call.func.attr}(); composers only instantiate and connect objects"))

        if not inspector.returns:
            message = "direct callable" if is_long_lived else "transactional handler"
            violations.append(("ARCH022", function.lineno, f"{function.name} must return a {message}"))
        elif is_long_lived:
            for return_node in inspector.returns:
                if _call_target(return_node.value) in contract.allowed_handlers:
                    violations.append(("ARCH020", return_node.lineno, f"{function.name} is long-lived and cannot return a transactional handler"))
        else:
            for return_node in inspector.returns:
                returned_handler = _call_target(return_node.value)
                if returned_handler not in contract.allowed_handlers:
                    violations.append(("ARCH022", return_node.lineno, f"{function.name} cannot return a raw controller, use case or callable"))
                elif returned_handler != expected_handler:
                    rule = "ARCH023" if is_stream else "ARCH021"
                    violations.append((rule, return_node.lineno, f"{function.name} must return {expected_handler}"))

        uow_assignments = [(name, value, line) for name, value, line in inspector.assignments if _uow_call(value, contract)]
        uow_names = {name for name, _, _ in uow_assignments}
        for async_with in inspector.async_with:
            for item in async_with.items:
                context = item.context_expr
                opens_uow = _uow_call(context, contract)
                if isinstance(context, ast.Name) and context.id in uow_names:
                    opens_uow = True
                if opens_uow:
                    violations.append(("ARCH024", async_with.lineno, f"{function.name} cannot open the UnitOfWork; the transactional handler owns it"))
                    break

        if is_long_lived:
            if uow_assignments:
                violations.append(("ARCH025", function.lineno, f"{function.name} is long-lived and cannot create a global UnitOfWork"))
            continue

        if len(uow_assignments) != 1:
            violations.append(("ARCH025", function.lineno, f"{function.name} must create exactly one configured UnitOfWork"))
            continue

        uow_name, uow_value, _ = uow_assignments[0]
        if (
            contract.uow_resource_names
            and isinstance(uow_value, ast.Call)
            and _call_target(uow_value) in set(contract.uow_types)
        ):
            resource = uow_value.args[0] if uow_value.args else None
            allowed_resources = set(contract.uow_resource_names)
            if not isinstance(resource, ast.Name) or resource.id not in allowed_resources:
                violations.append(("ARCH052", uow_value.lineno, f"{function.name} must create its UnitOfWork from a canonical process resource: {', '.join(sorted(allowed_resources))}"))

        if contract.forbid_uow_attribute_access:
            for attribute in inspector.attributes:
                if isinstance(attribute.value, ast.Name) and attribute.value.id == uow_name:
                    violations.append(("ARCH029", attribute.lineno, f"{function.name} cannot use UnitOfWork as a repository/service locator ({uow_name}.{attribute.attr})"))

        if contract.require_repository_uow_argument:
            for _, value, line in inspector.assignments:
                if not isinstance(value, ast.Call) or not _is_repository_call(value, contract):
                    continue
                first_arg = value.args[0] if value.args else None
                if not isinstance(first_arg, ast.Name) or first_arg.id != uow_name:
                    target = _expression_name(value.func) or "repository"
                    violations.append(("ARCH036", line, f"{function.name} must construct {target} with the same UnitOfWork as its first argument"))

        for return_node in inspector.returns:
            if _call_target(return_node.value) not in contract.allowed_handlers:
                continue
            call = return_node.value
            assert isinstance(call, ast.Call)
            handler_uow: ast.AST | None = call.args[0] if call.args else None
            if handler_uow is None:
                for keyword in call.keywords:
                    if keyword.arg in {"uow", "unit_of_work"}:
                        handler_uow = keyword.value
                        break
            if not isinstance(handler_uow, ast.Name) or handler_uow.id != uow_name:
                violations.append(("ARCH025", return_node.lineno, f"{function.name} must pass the same UnitOfWork to its transactional handler"))

    return tuple(violations)


def _composer_function_names(policy: ArchitecturePolicy, contract: ComposerContract) -> set[str]:
    names: set[str] = set()
    for file in sorted(policy.root.rglob("*.py")):
        relative = file.relative_to(policy.root).as_posix()
        if not any(fnmatch(relative, pattern) for pattern in contract.source_globs):
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_") and node.name.endswith(contract.function_suffix):
                names.add(node.name)
    return names


def _zero_arg_callsite_violations(project_root: Path, policy: ArchitecturePolicy, contract: ComposerContract) -> tuple[tuple[Path, int, str], ...]:
    if not contract.enforce_zero_arg_callsites:
        return ()
    composer_names = _composer_function_names(policy, contract)
    if not composer_names:
        return ()
    source_root = project_root / "src"
    if not source_root.is_dir():
        return ()
    violations: list[tuple[Path, int, str]] = []
    for file in sorted(source_root.rglob("*.py")):
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = _short_name(_expression_name(node.func))
            if called not in composer_names or (not node.args and not node.keywords):
                continue
            violations.append((file, node.lineno, f"{called} must be invoked with zero arguments; callers cannot inject infrastructure or operation data into composers"))
    return tuple(violations)


class ArchitectureChecker:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()

    def check(self, policy: ArchitecturePolicy) -> QualityGateResult:
        root = policy.root.resolve()
        violations: list[Violation] = []

        if not root.is_dir():
            return QualityGateResult(module=policy.name, violations=(Violation("ARCH001", str(root), 0, f"module root does not exist: {root}"),))

        for layer in policy.required_layers:
            layer_path = root / layer
            if not layer_path.is_dir():
                violations.append(self._violation("ARCH001", layer_path, 0, f"required layer {layer!r} is missing"))

        for pattern in policy.forbidden_paths:
            for forbidden in sorted(root.glob(pattern)):
                violations.append(self._violation("ARCH017", forbidden, 0, f"deprecated architecture path is forbidden: {pattern}"))

        imports_by_file: dict[Path, tuple[ImportReference, ...]] = {}
        for file in sorted(root.rglob("*.py")):
            try:
                tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
            except (SyntaxError, UnicodeDecodeError) as exc:
                violations.append(self._violation("ARCH000", file, 0, f"cannot parse Python source: {exc}"))
                continue

            imports = _extract_imports(policy, file, tree)
            imports_by_file[file] = imports
            relative = file.relative_to(root).as_posix()
            rule = policy.rule_for(relative)
            if rule is None:
                violations.append(self._violation("ARCH001", file, 0, f"no architecture import rule matches {relative}"))
                continue

            if policy.composer_contract is not None:
                for rule_id, line, message in _composer_violations(policy.composer_contract, relative, tree):
                    violations.append(self._violation(rule_id, file, line, message))

            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and policy.forbid_dynamic_imports and _is_dynamic_import(node):
                    violations.append(self._violation("ARCH012", file, node.lineno, "dynamic imports are forbidden in governed modules"))

            for imported in imports:
                if imported.wildcard and policy.forbid_wildcard_imports:
                    violations.append(self._violation("ARCH011", file, imported.line, f"wildcard import from {imported.module!r} is forbidden"))

                cross_target = _cross_module_target(policy, imported.module)
                if cross_target and policy.forbid_cross_module_imports:
                    violations.append(self._violation("ARCH008", file, imported.line, f"{policy.name} cannot import bounded context {cross_target!r}"))
                    continue

                message = _rule_violation(rule, imported.module)
                if message:
                    violations.append(self._violation(rule.rule_id, file, imported.line, message))

        if policy.composer_contract is not None:
            for file, line, message in _zero_arg_callsite_violations(self.project_root, policy, policy.composer_contract):
                violations.append(self._violation("ARCH057", file, line, message))

        for rule_id, path, line, message in check_semantic_contracts(self.project_root, policy):
            violations.append(self._violation(rule_id, path, line, message))

        if policy.forbid_cycles:
            graph = self._build_graph(policy, imports_by_file)
            for component in strongly_connected_components(graph):
                anchor = self.project_root / component[0]
                violations.append(self._violation("ARCH016", anchor, 0, "dependency cycle detected: " + " -> ".join(component)))

        return QualityGateResult(policy.name, tuple(sorted(set(violations))))

    def _build_graph(self, policy: ArchitecturePolicy, imports_by_file: dict[Path, tuple[ImportReference, ...]]) -> dict[str, set[str]]:
        module_to_file: dict[str, Path] = {_module_name_for_file(policy, file): file for file in imports_by_file}
        graph: dict[str, set[str]] = {self._relative(file): set() for file in imports_by_file}

        for source, imports in imports_by_file.items():
            source_key = self._relative(source)
            for imported in imports:
                target = module_to_file.get(imported.module)
                if target is None:
                    parts = imported.module.split(".")
                    while len(parts) > 1 and target is None:
                        parts.pop()
                        target = module_to_file.get(".".join(parts))
                if target is not None:
                    graph[source_key].add(self._relative(target))
        return graph

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.project_root).as_posix()
        except ValueError:
            return path.as_posix()

    def _violation(self, rule_id: str, path: Path, line: int, message: str) -> Violation:
        return Violation(rule_id, self._relative(path), line, message)


def _format_result(result: QualityGateResult) -> str:
    lines = [f"Module: {result.module}"]
    if result.passed:
        lines.extend(["Violations: 0", "RESULT: PASS"])
        return "\n".join(lines)

    lines.append(f"Violations: {len(result.violations)}")
    for violation in result.violations:
        location = violation.file if not violation.line else f"{violation.file}:{violation.line}"
        lines.append(f"- {violation.rule_id} {location} — {violation.message}")
    lines.append("RESULT: FAIL")
    return "\n".join(lines)


def run(project_root: Path, policy_dir: Path) -> int:
    checker = ArchitectureChecker(project_root)
    policies = load_policies(policy_dir, project_root=project_root)
    results = [checker.check(policy) for policy in policies]
    print("Woobe Architecture Quality Gate")
    print("=" * 31)
    for index, result in enumerate(results):
        if index:
            print()
        print(_format_result(result))
    return 0 if all(result.passed for result in results) else 1


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Woobe architecture policies")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--policy-dir", type=Path, default=Path("quality_gate/architecture/policies"))
    args = parser.parse_args(list(argv) if argv is not None else None)
    project_root = args.project_root.resolve()
    policy_dir = args.policy_dir
    if not policy_dir.is_absolute():
        policy_dir = project_root / policy_dir
    return run(project_root, policy_dir)


if __name__ == "__main__":
    sys.exit(main())
