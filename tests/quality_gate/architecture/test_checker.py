from pathlib import Path

from quality_gate.architecture.checker import ArchitectureChecker
from quality_gate.architecture.policy import load_policy


POLICY = """
[module]
name = "agent"
root = "src/modules/agent"
package = "modules.agent"
required_layers = ["domain", "application", "infra", "presentation", "composition"]

[constraints]
forbid_cross_module_imports = true
forbid_dynamic_imports = true
forbid_wildcard_imports = true
forbid_cycles = true
forbidden_paths = ["application/composers"]

[composer_contract]
source = ["composition/**"]
function_suffix = "_composer"
streaming_suffix = "_stream_composer"
allowed_handlers = ["TransactionalHandler", "StreamingTransactionalHandler"]
regular_handler = "TransactionalHandler"
streaming_handler = "StreamingTransactionalHandler"
uow_types = ["AgentUnitOfWork"]

[[rules]]
id = "ARCH006"
description = "routes"
source = ["presentation/routes.py"]
allow = ["modules.agent.presentation", "modules.agent.composition"]
deny = ["modules.agent.infra", "modules.agent.application", "modules.agent.domain"]

[[rules]]
id = "ARCH005"
description = "controllers"
source = ["presentation/controllers/**"]
allow = ["modules.agent.presentation", "modules.agent.application.interfaces", "modules.agent.application.dtos"]
deny = ["modules.agent.infra", "modules.agent.composition", "modules.agent.application.use_cases"]

[[rules]]
id = "ARCH019"
description = "composition"
source = ["composition/**"]
allow = ["modules.agent.domain", "modules.agent.application", "modules.agent.infra", "modules.agent.presentation.controllers", "shared"]
deny = ["modules.agent.presentation.routes"]

[[rules]]
id = "ARCH002"
description = "domain"
source = ["domain/**"]
allow = ["modules.agent.domain"]
deny = ["modules.agent.application", "modules.agent.infra", "modules.agent.presentation", "modules.agent.composition", "shared"]

[[rules]]
id = "ARCH003"
description = "application"
source = ["application/**"]
allow = ["modules.agent.application", "modules.agent.domain"]
deny = ["modules.agent.infra", "modules.agent.presentation", "modules.agent.composition", "sqlalchemy"]

[[rules]]
id = "ARCH004"
description = "infra"
source = ["infra/**"]
allow = ["modules.agent.infra", "modules.agent.application", "modules.agent.domain"]
deny = ["modules.agent.presentation", "modules.agent.composition"]
"""


def _module(tmp_path: Path) -> tuple[ArchitectureChecker, object]:
    root = tmp_path / "src/modules/agent"
    for layer in ("domain", "application", "infra", "presentation/controllers", "composition"):
        (root / layer).mkdir(parents=True, exist_ok=True)
    policy_file = tmp_path / "agent.toml"
    policy_file.write_text(POLICY, encoding="utf-8")
    return ArchitectureChecker(tmp_path), load_policy(policy_file, project_root=tmp_path)


def test_route_to_composition_is_allowed(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    (root / "presentation/routes.py").write_text(
        "from modules.agent.composition.create_agent import create_agent\n",
        encoding="utf-8",
    )
    (root / "composition/create_agent.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "domain/entities.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "application/use_case.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "infra/repository.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "presentation/controllers/create.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = checker.check(policy)

    assert result.passed, result.violations


def test_application_to_infra_is_rejected(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    (root / "application/use_case.py").write_text(
        "from modules.agent.infra.repository import Repository\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH003" for item in result.violations)


def test_cross_bounded_context_import_is_rejected(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    (root / "application/use_case.py").write_text(
        "from modules.network.domain.entities import Network\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH008" for item in result.violations)


def test_dynamic_and_wildcard_imports_are_rejected(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    (root / "application/use_case.py").write_text(
        "import importlib\nfrom modules.agent.domain import *\nimportlib.import_module('modules.agent.infra.x')\n",
        encoding="utf-8",
    )

    result = checker.check(policy)
    ids = {item.rule_id for item in result.violations}

    assert "ARCH011" in ids
    assert "ARCH012" in ids


def test_deprecated_path_is_rejected(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    (root / "application/composers").mkdir()
    (root / "application/composers/create.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH017" for item in result.violations)


def test_relative_imports_are_resolved_before_policy_check(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    use_cases = root / "application/use_cases"
    use_cases.mkdir(exist_ok=True)
    (use_cases / "service.py").write_text(
        "from ...infra.repository import Repository\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH003" for item in result.violations)


def test_imports_inside_type_checking_and_functions_are_enforced(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    (root / "application/use_case.py").write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from modules.agent.infra.repository import Repository\n"
        "def load():\n"
        "    from modules.agent.infra.repository import OtherRepository\n",
        encoding="utf-8",
    )

    result = checker.check(policy)
    violations = [item for item in result.violations if item.rule_id == "ARCH003"]

    assert len(violations) == 2


def test_internal_dependency_cycle_is_rejected(tmp_path: Path) -> None:
    checker, policy = _module(tmp_path)
    root = tmp_path / "src/modules/agent"
    (root / "application/a.py").write_text(
        "from modules.agent.application.b import VALUE\n",
        encoding="utf-8",
    )
    (root / "application/b.py").write_text(
        "from modules.agent.application.a import VALUE\n",
        encoding="utf-8",
    )

    result = checker.check(policy)

    assert any(item.rule_id == "ARCH016" for item in result.violations)


def _write_composer(tmp_path: Path, source: str) -> tuple[ArchitectureChecker, object]:
    checker, policy = _module(tmp_path)
    (tmp_path / "src/modules/agent/composition/example.py").write_text(source, encoding="utf-8")
    return checker, policy


def test_transactional_composer_contract_passes(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer(factory) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    return TransactionalHandler(uow, handler)\n",
    )
    result = checker.check(policy)
    assert result.passed, result.violations


def test_streaming_composer_contract_passes(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.streaming_transactional_handler import StreamingTransactionalHandler\n"
        "def ask_stream_composer(factory) -> StreamingTransactionalHandler:\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    return StreamingTransactionalHandler(uow, handler)\n",
    )
    result = checker.check(policy)
    assert result.passed, result.violations


def test_composer_without_transactional_annotation_is_rejected(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer(factory):\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    return TransactionalHandler(uow, handler)\n",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH021" for item in result.violations)


def test_composer_returning_raw_callable_is_rejected(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "def create_agent_composer(factory) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    return controller.handle\n",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH022" for item in result.violations)


def test_async_composer_is_rejected(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "async def create_agent_composer(factory) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    return TransactionalHandler(uow, handler)\n",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH022" for item in result.violations)


def test_stream_composer_must_use_streaming_handler(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def ask_stream_composer(factory) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    return TransactionalHandler(uow, handler)\n",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH023" for item in result.violations)


def test_nested_runtime_helper_may_manage_its_own_short_uow(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer(factory) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    async def handler(request):\n"
        "        async with AgentUnitOfWork(factory):\n"
        "            return request\n"
        "    return TransactionalHandler(uow, handler)\n",
    )
    result = checker.check(policy)
    assert result.passed, result.violations


def test_composer_body_cannot_open_uow_itself(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "async def create_agent_composer(factory) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(factory)\n"
        "    async with uow:\n"
        "        value = 1\n"
        "    return TransactionalHandler(uow, handler)\n",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH024" for item in result.violations)


def test_composer_must_use_one_uow_for_transaction_boundary(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n"
        "from shared.infra.transactional_handler import TransactionalHandler\n"
        "def create_agent_composer(factory) -> TransactionalHandler:\n"
        "    repository_uow = AgentUnitOfWork(factory)\n"
        "    handler_uow = AgentUnitOfWork(factory)\n"
        "    return TransactionalHandler(handler_uow, handler)\n",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH025" for item in result.violations)


def test_non_composer_helper_is_ignored(tmp_path: Path) -> None:
    checker, policy = _write_composer(
        tmp_path,
        "async def build_runtime(factory):\n"
        "    return await factory()\n",
    )
    result = checker.check(policy)
    assert result.passed, result.violations
