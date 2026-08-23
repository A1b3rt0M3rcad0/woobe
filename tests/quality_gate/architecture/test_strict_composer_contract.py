from pathlib import Path

from quality_gate.architecture.checker import ArchitectureChecker
from quality_gate.architecture.policy import load_policy


STRICT_POLICY = """
[module]
name = "agent"
root = "src/modules/agent"
package = "modules.agent"
required_layers = ["domain", "application", "infra", "presentation", "composition"]

[constraints]
forbid_cross_module_imports = true
forbid_dynamic_imports = true
forbid_wildcard_imports = true
forbid_cycles = false
forbidden_paths = []

[composer_contract]
source = ["composition/composers/**"]
function_suffix = "_composer"
streaming_suffix = "_stream_composer"
allowed_handlers = ["TransactionalHandler", "StreamingTransactionalHandler"]
regular_handler = "TransactionalHandler"
streaming_handler = "StreamingTransactionalHandler"
uow_types = ["AgentUnitOfWork"]
repository_suffixes = ["Repository", "Writer"]
forbid_control_flow = true
forbid_nested_definitions = true
forbid_uow_attribute_access = true
require_repository_uow_argument = true
require_zero_arguments = true
dependency_parameter_tokens = ["database", "settings", "executor", "factory", "repo", "uow"]
uow_resource_names = ["DATABASE_ENGINE"]
forbid_module_level_transients = true
transient_suffixes = ["UnitOfWork", "Repository", "UseCase", "Controller", "Handler", "Service"]
forbid_composed_dependency_calls = true
enforce_zero_arg_callsites = true
forbidden_module_level_calls = ["Settings", "create_engine"]

[[rules]]
id = "ARCH026"
description = "composition"
source = ["composition/**"]
allow = ["modules.agent", "shared"]
deny = []

[[rules]]
id = "ARCH002"
description = "domain"
source = ["domain/**"]
allow = ["modules.agent.domain"]
deny = []

[[rules]]
id = "ARCH003"
description = "application"
source = ["application/**"]
allow = ["modules.agent.application", "modules.agent.domain"]
deny = []

[[rules]]
id = "ARCH004"
description = "infra"
source = ["infra/**"]
allow = ["modules.agent.infra", "modules.agent.application", "modules.agent.domain"]
deny = []

[[rules]]
id = "ARCH006"
description = "presentation"
source = ["presentation/**"]
allow = ["modules.agent.presentation", "modules.agent.application"]
deny = []
"""


def _checker(tmp_path: Path) -> tuple[ArchitectureChecker, object, Path]:
    root = tmp_path / "src/modules/agent"
    for layer in ("domain", "application", "infra", "presentation", "composition/composers"):
        (root / layer).mkdir(parents=True, exist_ok=True)
    policy_file = tmp_path / "agent.toml"
    policy_file.write_text(STRICT_POLICY, encoding="utf-8")
    return ArchitectureChecker(tmp_path), load_policy(policy_file, project_root=tmp_path), root


def _write_valid_composer(root: Path) -> None:
    (root / "composition/composers/create_agent.py").write_text(
        "from modules.agent.composition.resources import DATABASE_ENGINE\n"
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from modules.agent.infra.database.repositories import SQLAlchemyAgentRepository\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer() -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(DATABASE_ENGINE)\n"
        "    repo = SQLAlchemyAgentRepository(uow)\n"
        "    controller = Controller(repo)\n"
        "    return TransactionalHandler(uow, controller.handle)\n",
        encoding="utf-8",
    )


def test_zero_argument_composer_with_process_resource_passes(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    _write_valid_composer(root)

    result = checker.check(policy)

    assert result.passed, result.violations


def test_dependency_parameter_is_rejected(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    (root / "composition/composers/create_agent.py").write_text(
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer(database) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(database)\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH051" for item in result.violations)


def test_operation_parameter_is_rejected(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    (root / "composition/composers/create_agent.py").write_text(
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer(project_id) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(DATABASE_ENGINE)\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH062" for item in result.violations)


def test_uow_must_use_canonical_process_resource(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    (root / "composition/composers/create_agent.py").write_text(
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer() -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(OTHER_ENGINE)\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH052" for item in result.violations)


def test_module_scope_transaction_objects_are_rejected(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    (root / "composition/composers/create_agent.py").write_text(
        "GLOBAL_UOW = AgentUnitOfWork(DATABASE_ENGINE)\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer() -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(DATABASE_ENGINE)\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH054" for item in result.violations)


def test_process_resource_factory_in_composer_module_is_rejected(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    (root / "composition/composers/create_agent.py").write_text(
        "DATABASE_ENGINE = create_engine()\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer() -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(DATABASE_ENGINE)\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH061" for item in result.violations)


def test_composer_cannot_execute_composed_dependency(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    (root / "composition/composers/create_agent.py").write_text(
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer() -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(DATABASE_ENGINE)\n"
        "    use_case = CreateAgentUseCase()\n"
        "    use_case.configure()\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH059" for item in result.violations)


def test_composer_callsite_cannot_inject_dependencies(tmp_path: Path) -> None:
    checker, policy, root = _checker(tmp_path)
    _write_valid_composer(root)
    (tmp_path / "src/main.py").write_text(
        "from modules.agent.composition.composers.create_agent import create_agent_composer\n"
        "handler = create_agent_composer(database)\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH057" for item in result.violations)
