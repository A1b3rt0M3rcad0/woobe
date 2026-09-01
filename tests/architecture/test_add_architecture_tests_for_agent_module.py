"""Package-aware architecture guards for the Agent bounded context."""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
SRC_AGENT = SRC_MODULES / "agent"

KNOWN_MODULES = {
    path.name
    for path in SRC_MODULES.iterdir()
    if path.is_dir() and not path.name.startswith("_")
}
LEGACY_MODULES = {"ai", "knowledge", "runtime"}
AGENT_REQUIRED_LAYERS = {"domain", "application", "infra", "presentation", "composition"}
LAYER_FORBIDDEN = {
    "domain": {"infra", "presentation", "application", "composition"},
    "application": {"infra", "presentation", "composition"},
}


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _python_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _imports(path: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return ()
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
        elif isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
    return tuple(values)


class TestAddArchitectureTestsForAgentModule:
    def test_agent_module_and_required_layers_exist(self):
        assert SRC_AGENT.is_dir(), "Agent module must live in packages/woobe-core/src/modules/agent"
        present = {
            path.name for path in SRC_AGENT.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        }
        missing = AGENT_REQUIRED_LAYERS - present
        assert not missing, f"Agent module missing required layers: {missing}"

    def test_agent_does_not_import_other_bounded_contexts(self):
        forbidden_targets = KNOWN_MODULES - {"agent", *LEGACY_MODULES}
        violations = []
        for py_file in _python_files(SRC_AGENT):
            for imported in _imports(py_file):
                parts = imported.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in forbidden_targets:
                    violations.append(
                        f"{_relative(py_file)} imports forbidden bounded context {parts[1]} via {imported}"
                    )
        assert not violations, (
            "Agent must not statically import another bounded context:\n"
            + "\n".join(violations[:30])
        )

    def test_agent_does_not_import_removed_legacy_modules(self):
        violations = []
        for py_file in _python_files(SRC_AGENT):
            for imported in _imports(py_file):
                parts = imported.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(f"{_relative(py_file)} imports {imported}")
        assert not violations, (
            "Agent imports removed legacy bounded contexts:\n"
            + "\n".join(violations[:30])
        )

    def test_domain_and_application_layer_isolation(self):
        violations = []
        for source_layer, forbidden_layers in LAYER_FORBIDDEN.items():
            for py_file in _python_files(SRC_AGENT / source_layer):
                for imported in _imports(py_file):
                    parts = imported.split(".")
                    if (
                        len(parts) >= 3
                        and parts[0] == "modules"
                        and parts[1] == "agent"
                        and parts[2] in forbidden_layers
                    ):
                        violations.append(
                            f"{_relative(py_file)}: {source_layer} imports {parts[2]} via {imported}"
                        )
        assert not violations, (
            "Agent inner layers depend on outer layers:\n"
            + "\n".join(violations[:30])
        )

    def test_agent_unit_of_work_is_bounded_context_local(self):
        uow_file = SRC_AGENT / "infra" / "database" / "unit_of_work.py"
        assert uow_file.is_file(), "AgentUnitOfWork implementation must exist"
        module_imports = set()
        for imported in _imports(uow_file):
            parts = imported.split(".")
            if len(parts) >= 2 and parts[0] == "modules" and parts[1] != "agent":
                module_imports.add(parts[1])
        assert not module_imports, (
            f"Agent UoW imports non-Agent bounded contexts: {module_imports}"
        )

    def test_agent_infra_and_presentation_surfaces_exist(self):
        infra = SRC_AGENT / "infra"
        for required in ("database", "messaging", "workers"):
            assert (infra / required).is_dir(), f"Agent infra missing {required}"
        presentation = SRC_AGENT / "presentation"
        assert presentation.is_dir()
        assert (presentation / "routes.py").is_file()
        assert (presentation / "schemas.py").is_file()
        assert (presentation / "controllers").is_dir()


class TestAddArchitectureTestsForAgentModuleRejectsForbidden:
    def test_detects_agent_domain_importing_infra(self):
        tree = ast.parse("from modules.agent.infra.database.models import AgentModel\n")
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("modules.agent.infra")
            for node in ast.walk(tree)
        )

    def test_detects_agent_importing_non_agent_module(self):
        tree = ast.parse("from modules.billing.infra.repositories import BillingRepository\n")
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("modules.billing")
            for node in ast.walk(tree)
        )
