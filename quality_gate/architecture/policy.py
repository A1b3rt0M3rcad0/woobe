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
    forbidden_parameter_types: tuple[str, ...] = ()
    forbidden_parameter_names: tuple[str, ...] = ()
    forbidden_calls: tuple[str, ...] = ()
    repository_suffixes: tuple[str, ...] = ("Repository", "Writer")
    forbid_control_flow: bool = False
    forbid_nested_definitions: bool = False
    forbid_uow_attribute_access: bool = False
    require_repository_uow_argument: bool = False
    require_zero_arguments: bool = False
    dependency_parameter_tokens: tuple[str, ...] = ()
    uow_resource_names: tuple[str, ...] = ()
    forbid_module_level_transients: bool = False
    transient_suffixes: tuple[str, ...] = ()
    forbid_composed_dependency_calls: bool = False
    enforce_zero_arg_callsites: bool = False
    forbidden_module_level_calls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnitOfWorkContract:
    interface_files: tuple[str, ...]
    deprecated_interface_files: tuple[str, ...]
    concrete_sources: tuple[str, ...]
    forbidden_interface_imports: tuple[str, ...]
    repository_name_fragments: tuple[str, ...]
    allowed_properties: tuple[str, ...] = ("session",)
    forbid_repository_imports: bool = True
    forbid_repository_properties: bool = True


@dataclass(frozen=True, slots=True)
class RepositoryContract:
    interface_sources: tuple[str, ...]
    concrete_sources: tuple[str, ...]
    external_base_files: tuple[str, ...]
    concrete_name_prefixes: tuple[str, ...]
    excluded_port_bases: tuple[str, ...]
    forbidden_interface_imports: tuple[str, ...]
    forbidden_constructor_types: tuple[str, ...]
    forbidden_transaction_methods: tuple[str, ...]
    require_application_port_base: bool = True
    require_uow_constructor: bool = True


@dataclass(frozen=True, slots=True)
class ApplicationContract:
    source_globs: tuple[str, ...]
    dependency_name_tokens: tuple[str, ...]
    forbid_untyped_dependencies: bool = True


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
    unit_of_work_contract: UnitOfWorkContract | None = None
    repository_contract: RepositoryContract | None = None
    application_contract: ApplicationContract | None = None

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

    repository_suffixes = _string_tuple(value.get("repository_suffixes"), field="composer_contract.repository_suffixes") or ("Repository", "Writer")

    return ComposerContract(
        source_globs=source_globs,
        function_suffix=_required_string(value.get("function_suffix"), field="composer_contract.function_suffix"),
        streaming_suffix=_required_string(value.get("streaming_suffix"), field="composer_contract.streaming_suffix"),
        allowed_handlers=allowed_handlers,
        regular_handler=regular_handler,
        streaming_handler=streaming_handler,
        uow_types=uow_types,
        forbidden_parameter_types=_string_tuple(value.get("forbidden_parameter_types"), field="composer_contract.forbidden_parameter_types"),
        forbidden_parameter_names=_string_tuple(value.get("forbidden_parameter_names"), field="composer_contract.forbidden_parameter_names"),
        forbidden_calls=_string_tuple(value.get("forbidden_calls"), field="composer_contract.forbidden_calls"),
        repository_suffixes=repository_suffixes,
        forbid_control_flow=bool(value.get("forbid_control_flow", False)),
        forbid_nested_definitions=bool(value.get("forbid_nested_definitions", False)),
        forbid_uow_attribute_access=bool(value.get("forbid_uow_attribute_access", False)),
        require_repository_uow_argument=bool(value.get("require_repository_uow_argument", False)),
        require_zero_arguments=bool(value.get("require_zero_arguments", False)),
        dependency_parameter_tokens=_string_tuple(value.get("dependency_parameter_tokens"), field="composer_contract.dependency_parameter_tokens"),
        uow_resource_names=_string_tuple(value.get("uow_resource_names"), field="composer_contract.uow_resource_names"),
        forbid_module_level_transients=bool(value.get("forbid_module_level_transients", False)),
        transient_suffixes=_string_tuple(value.get("transient_suffixes"), field="composer_contract.transient_suffixes"),
        forbid_composed_dependency_calls=bool(value.get("forbid_composed_dependency_calls", False)),
        enforce_zero_arg_callsites=bool(value.get("enforce_zero_arg_callsites", False)),
        forbidden_module_level_calls=_string_tuple(value.get("forbidden_module_level_calls"), field="composer_contract.forbidden_module_level_calls"),
    )


def _load_uow_contract(path: Path, value: object) -> UnitOfWorkContract | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise PolicyError(f"{path}: [unit_of_work_contract] must be a table")
    interface_files = _string_tuple(value.get("interface_files"), field="unit_of_work_contract.interface_files")
    concrete_sources = _string_tuple(value.get("concrete_sources"), field="unit_of_work_contract.concrete_sources")
    if not interface_files or not concrete_sources:
        raise PolicyError(f"{path}: unit_of_work_contract requires interface_files and concrete_sources")
    return UnitOfWorkContract(
        interface_files=interface_files,
        deprecated_interface_files=_string_tuple(value.get("deprecated_interface_files"), field="unit_of_work_contract.deprecated_interface_files"),
        concrete_sources=concrete_sources,
        forbidden_interface_imports=_string_tuple(value.get("forbidden_interface_imports"), field="unit_of_work_contract.forbidden_interface_imports"),
        repository_name_fragments=_string_tuple(value.get("repository_name_fragments"), field="unit_of_work_contract.repository_name_fragments") or ("Repository", "Writer"),
        allowed_properties=_string_tuple(value.get("allowed_properties"), field="unit_of_work_contract.allowed_properties") or ("session",),
        forbid_repository_imports=bool(value.get("forbid_repository_imports", True)),
        forbid_repository_properties=bool(value.get("forbid_repository_properties", True)),
    )


def _load_repository_contract(path: Path, value: object) -> RepositoryContract | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise PolicyError(f"{path}: [repository_contract] must be a table")
    interface_sources = _string_tuple(value.get("interface_sources"), field="repository_contract.interface_sources")
    concrete_sources = _string_tuple(value.get("concrete_sources"), field="repository_contract.concrete_sources")
    if not interface_sources or not concrete_sources:
        raise PolicyError(f"{path}: repository_contract requires interface_sources and concrete_sources")
    return RepositoryContract(
        interface_sources=interface_sources,
        concrete_sources=concrete_sources,
        external_base_files=_string_tuple(value.get("external_base_files"), field="repository_contract.external_base_files"),
        concrete_name_prefixes=_string_tuple(value.get("concrete_name_prefixes"), field="repository_contract.concrete_name_prefixes") or ("SQLAlchemy",),
        excluded_port_bases=_string_tuple(value.get("excluded_port_bases"), field="repository_contract.excluded_port_bases") or ("BaseSQLAlchemyRepository", "SqlAlchemyRepositoryBase"),
        forbidden_interface_imports=_string_tuple(value.get("forbidden_interface_imports"), field="repository_contract.forbidden_interface_imports"),
        forbidden_constructor_types=_string_tuple(value.get("forbidden_constructor_types"), field="repository_contract.forbidden_constructor_types"),
        forbidden_transaction_methods=_string_tuple(value.get("forbidden_transaction_methods"), field="repository_contract.forbidden_transaction_methods") or ("commit", "rollback"),
        require_application_port_base=bool(value.get("require_application_port_base", True)),
        require_uow_constructor=bool(value.get("require_uow_constructor", True)),
    )


def _load_application_contract(path: Path, value: object) -> ApplicationContract | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise PolicyError(f"{path}: [application_contract] must be a table")
    sources = _string_tuple(value.get("source"), field="application_contract.source")
    if not sources:
        raise PolicyError(f"{path}: application_contract.source cannot be empty")
    return ApplicationContract(
        source_globs=sources,
        dependency_name_tokens=_string_tuple(value.get("dependency_name_tokens"), field="application_contract.dependency_name_tokens") or (
            "repo", "repository", "reader", "writer", "factory", "executor", "storage", "cipher", "publisher", "clock"
        ),
        forbid_untyped_dependencies=bool(value.get("forbid_untyped_dependencies", True)),
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
        name=str(name),
        root=root,
        package=str(package),
        required_layers=required_layers,
        forbidden_paths=_string_tuple(constraints.get("forbidden_paths"), field="constraints.forbidden_paths"),
        forbid_cross_module_imports=bool(constraints.get("forbid_cross_module_imports", True)),
        forbid_dynamic_imports=bool(constraints.get("forbid_dynamic_imports", True)),
        forbid_wildcard_imports=bool(constraints.get("forbid_wildcard_imports", True)),
        forbid_cycles=bool(constraints.get("forbid_cycles", True)),
        rules=tuple(rules),
        composer_contract=_load_composer_contract(path, data.get("composer_contract")),
        unit_of_work_contract=_load_uow_contract(path, data.get("unit_of_work_contract")),
        repository_contract=_load_repository_contract(path, data.get("repository_contract")),
        application_contract=_load_application_contract(path, data.get("application_contract")),
    )


def load_policies(policy_dir: Path, *, project_root: Path | None = None) -> tuple[ArchitecturePolicy, ...]:
    policy_dir = Path(policy_dir)
    policies = tuple(load_policy(path, project_root=project_root) for path in sorted(policy_dir.glob("*.toml")))
    if not policies:
        raise PolicyError(f"no architecture policies found in {policy_dir}")
    return policies
