from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

from .graph import strongly_connected_components
from .policy import ArchitecturePolicy, ImportRule, load_policies


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
            module = (
                _resolve_relative_import(policy, file, node)
                if node.level
                else (node.module or "")
            )
            if module:
                imports.append(
                    ImportReference(
                        module=module,
                        line=node.lineno,
                        wildcard=any(alias.name == "*" for alias in node.names),
                    )
                )
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


class ArchitectureChecker:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()

    def check(self, policy: ArchitecturePolicy) -> QualityGateResult:
        root = policy.root.resolve()
        violations: list[Violation] = []

        if not root.is_dir():
            return QualityGateResult(
                module=policy.name,
                violations=(
                    Violation("ARCH001", str(root), 0, f"module root does not exist: {root}"),
                ),
            )

        for layer in policy.required_layers:
            layer_path = root / layer
            if not layer_path.is_dir():
                violations.append(
                    self._violation("ARCH001", layer_path, 0, f"required layer {layer!r} is missing")
                )

        for pattern in policy.forbidden_paths:
            for forbidden in sorted(root.glob(pattern)):
                violations.append(
                    self._violation("ARCH017", forbidden, 0, f"deprecated architecture path is forbidden: {pattern}")
                )

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
                violations.append(
                    self._violation("ARCH001", file, 0, f"no architecture import rule matches {relative}")
                )
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and policy.forbid_dynamic_imports and _is_dynamic_import(node):
                    violations.append(
                        self._violation("ARCH012", file, node.lineno, "dynamic imports are forbidden in governed modules")
                    )

            for imported in imports:
                if imported.wildcard and policy.forbid_wildcard_imports:
                    violations.append(
                        self._violation("ARCH011", file, imported.line, f"wildcard import from {imported.module!r} is forbidden")
                    )

                cross_target = _cross_module_target(policy, imported.module)
                if cross_target and policy.forbid_cross_module_imports:
                    violations.append(
                        self._violation(
                            "ARCH008",
                            file,
                            imported.line,
                            f"{policy.name} cannot import bounded context {cross_target!r}",
                        )
                    )
                    continue

                message = _rule_violation(rule, imported.module)
                if message:
                    violations.append(self._violation(rule.rule_id, file, imported.line, message))

        if policy.forbid_cycles:
            graph = self._build_graph(policy, imports_by_file)
            for component in strongly_connected_components(graph):
                anchor = self.project_root / component[0]
                violations.append(
                    self._violation(
                        "ARCH016",
                        anchor,
                        0,
                        "dependency cycle detected: " + " -> ".join(component),
                    )
                )

        return QualityGateResult(policy.name, tuple(sorted(set(violations))))

    def _build_graph(
        self,
        policy: ArchitecturePolicy,
        imports_by_file: dict[Path, tuple[ImportReference, ...]],
    ) -> dict[str, set[str]]:
        module_to_file: dict[str, Path] = {
            _module_name_for_file(policy, file): file for file in imports_by_file
        }
        graph: dict[str, set[str]] = {
            self._relative(file): set() for file in imports_by_file
        }

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
    parser.add_argument(
        "--policy-dir",
        type=Path,
        default=Path("quality_gate/architecture/policies"),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    project_root = args.project_root.resolve()
    policy_dir = args.policy_dir
    if not policy_dir.is_absolute():
        policy_dir = project_root / policy_dir
    return run(project_root, policy_dir)


if __name__ == "__main__":
    sys.exit(main())
