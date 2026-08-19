from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


class PolicyError(ValueError):
    """Raised when an architecture policy is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class ImportRule:
    rule_id: str
    description: str
    source_globs: tuple[str, ...]
    allow_prefixes: tuple[str, ...]
    deny_prefixes: tuple[str, ...]
    enforce_internal_allowlist: bool = True


@dataclass(frozen=True, slots=True)
class ComposerContract:
    source_globs: tuple[str, ...]
    function_suffix: str
    streaming_suffix: str
    allowed_handlers: tuple[str, ...]
    regular_handler: str
    streaming_handler: str
    uow_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArchitecturePolicy:
    name: str
    root: Path
    package: str
    required_layers: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    forbid_cross_module_imports: bool
    forbid_dynamic_imports: bool
    forbid_wildcard_imports: bool
    forbid_cycles: bool
    rules: tuple[ImportRule, ...]
    composer_contract: ComposerContract | None = None

    @property
    def module_name(self) -> str:
        return self.package.split(".")[-1]

    def rule_for(self, relative_path: str) -> ImportRule | None:
        from fnmatch import fnmatch

        normalized = relative_path.replace("\\", "/")
        for rule in self.rules:
            if any(fnmatch(normalized, pattern) for pattern in rule.source_globs):
                return rule
        return None


def _string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PolicyError(f"{field} must be a list of strings")
    return tuple(value)


def _required_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise PolicyError(f"{field} is required")
    return value


def _load_composer_contract(path: Path, value: object) -> ComposerContract | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise PolicyError(f"{path}: [composer_contract] must be a table")

    source_globs = _string_tuple(value.get("source"), field="composer_contract.source")
    allowed_handlers = _string_tuple(value.get("allowed_handlers"), field="composer_contract.allowed_handlers")
    uow_types = _string_tuple(value.get("uow_types"), field="composer_contract.uow_types")
    if not source_globs:
        raise PolicyError(f"{path}: composer_contract.source cannot be empty")
    if not allowed_handlers:
        raise PolicyError(f"{path}: composer_contract.allowed_handlers cannot be empty")
    if not uow_types:
        raise PolicyError(f"{path}: composer_contract.uow_types cannot be empty")

    regular_handler = _required_string(value.get("regular_handler"), field="composer_contract.regular_handler")
    streaming_handler = _required_string(value.get("streaming_handler"), field="composer_contract.streaming_handler")
    if regular_handler not in allowed_handlers:
        raise PolicyError(f"{path}: composer_contract.regular_handler must be listed in allowed_handlers")
    if streaming_handler not in allowed_handlers:
        raise PolicyError(f"{path}: composer_contract.streaming_handler must be listed in allowed_handlers")

    return ComposerContract(
        source_globs=source_globs,
        function_suffix=_required_string(value.get("function_suffix"), field="composer_contract.function_suffix"),
        streaming_suffix=_required_string(value.get("streaming_suffix"), field="composer_contract.streaming_suffix"),
        allowed_handlers=allowed_handlers,
        regular_handler=regular_handler,
        streaming_handler=streaming_handler,
        uow_types=uow_types,
    )


def load_policy(path: Path, *, project_root: Path | None = None) -> ArchitecturePolicy:
    path = Path(path)
    with path.open("rb") as stream:
        data = tomllib.load(stream)

    module = data.get("module")
    constraints = data.get("constraints", {})
    raw_rules = data.get("rules", [])
    if not isinstance(module, dict):
        raise PolicyError(f"{path}: missing [module] table")
    if not isinstance(constraints, dict):
        raise PolicyError(f"{path}: [constraints] must be a table")
    if not isinstance(raw_rules, list):
        raise PolicyError(f"{path}: [[rules]] entries are required")

    name = module.get("name")
    root_value = module.get("root")
    package = module.get("package")
    if not all(isinstance(value, str) and value for value in (name, root_value, package)):
        raise PolicyError(f"{path}: module name, root and package are required strings")

    required_layers = _string_tuple(module.get("required_layers"), field="module.required_layers")
    if not required_layers:
        raise PolicyError(f"{path}: module.required_layers cannot be empty")

    rules: list[ImportRule] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise PolicyError(f"{path}: rules[{index}] must be a table")
        rule_id = raw.get("id")
        description = raw.get("description")
        if not isinstance(rule_id, str) or not rule_id:
            raise PolicyError(f"{path}: rules[{index}].id is required")
        if rule_id in seen_ids:
            raise PolicyError(f"{path}: duplicate rule id {rule_id}")
        seen_ids.add(rule_id)
        if not isinstance(description, str) or not description:
            raise PolicyError(f"{path}: rules[{index}].description is required")
        source_globs = _string_tuple(raw.get("source"), field=f"rules[{index}].source")
        if not source_globs:
            raise PolicyError(f"{path}: rules[{index}].source cannot be empty")
        rules.append(
            ImportRule(
                rule_id=rule_id,
                description=description,
                source_globs=source_globs,
                allow_prefixes=_string_tuple(raw.get("allow"), field=f"rules[{index}].allow"),
                deny_prefixes=_string_tuple(raw.get("deny"), field=f"rules[{index}].deny"),
                enforce_internal_allowlist=bool(raw.get("enforce_internal_allowlist", True)),
            )
        )

    root = Path(root_value)
    if project_root is not None:
        root = Path(project_root) / root

    return ArchitecturePolicy(
        name=name,
        root=root,
        package=package,
        required_layers=required_layers,
        forbidden_paths=_string_tuple(constraints.get("forbidden_paths"), field="constraints.forbidden_paths"),
        forbid_cross_module_imports=bool(constraints.get("forbid_cross_module_imports", True)),
        forbid_dynamic_imports=bool(constraints.get("forbid_dynamic_imports", True)),
        forbid_wildcard_imports=bool(constraints.get("forbid_wildcard_imports", True)),
        forbid_cycles=bool(constraints.get("forbid_cycles", True)),
        rules=tuple(rules),
        composer_contract=_load_composer_contract(path, data.get("composer_contract")),
    )


def load_policies(policy_dir: Path, *, project_root: Path | None = None) -> tuple[ArchitecturePolicy, ...]:
    policy_dir = Path(policy_dir)
    policies = tuple(load_policy(path, project_root=project_root) for path in sorted(policy_dir.glob("*.toml")))
    if not policies:
        raise PolicyError(f"no architecture policies found in {policy_dir}")
    return policies
