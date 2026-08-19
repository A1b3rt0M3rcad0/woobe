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
allow = ["modules.agent.domain", "modules.agent.application", "modules.agent.infra", "modules.agent.presentation.controllers"]
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
