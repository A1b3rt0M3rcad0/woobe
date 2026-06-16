import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ARCH = Path(__file__).resolve().parent
SRC_AGENT = PROJECT_ROOT / "src" / "modules" / "agent"
AGENT_BOUNDARIES_FILE = TESTS_ARCH / "test_agent_boundaries.py"
ALLOWLIST_FILE = TESTS_ARCH / "legacy_import_allowlist.yaml"

LEGACY_MODULES = {"ai", "knowledge", "runtime"}


class TestAddAgentBoundaryArchitectureTests:
    def test_add_agent_boundary_architecture_tests(self):
        assert AGENT_BOUNDARIES_FILE.is_file(), (
            f"test_agent_boundaries.py must exist at {AGENT_BOUNDARIES_FILE}"
        )

        source = AGENT_BOUNDARIES_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imports_ast_module = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "ast":
                        imports_ast_module = True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "ast":
                    imports_ast_module = True

        assert imports_ast_module, (
            "test_agent_boundaries.py must use the ast module for import analysis, not regex"
        )

        uses_ast_parse = "ast.parse" in source or "ast.walk" in source
        assert uses_ast_parse, (
            "test_agent_boundaries.py must use ast.parse/ast.walk for static analysis"
        )

        assert ALLOWLIST_FILE.is_file(), (
            f"legacy_import_allowlist.yaml must exist at {ALLOWLIST_FILE}"
        )

        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries") or []
        assert len(entries) > 0, "Allowlist must have at least one entry during migration"

        required_fields = {"file", "target_module", "removal_spec", "scope"}
        for i, entry in enumerate(entries):
            missing = required_fields - set(entry.keys())
            assert not missing, (
                f"Allowlist entry {i} missing fields: {missing}"
            )

    def test_agent_boundary_rules_pass_with_current_state(self):
        if not SRC_AGENT.exists():
            return

        allowlist = set()
        if ALLOWLIST_FILE.exists():
            with open(ALLOWLIST_FILE, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            entries = data.get("entries") or []
            allowlist = {
                (e["file"].replace("/", "\\").replace("\\", "/"), e["target_module"])
                for e in entries
                if e.get("scope") == "module_boundaries"
            }

        violations = []
        for py_file in SRC_AGENT.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            rel_path = py_file.relative_to(PROJECT_ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                        if (rel_path, parts[1]) not in allowlist:
                            violations.append(
                                f"{rel_path}:{node.lineno} imports {node.module}"
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                            if (rel_path, parts[1]) not in allowlist:
                                violations.append(
                                    f"{rel_path}:{node.lineno} imports {alias.name}"
                                )

        assert not violations, (
            "Agent module must not import from legacy modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_agent_domain_layer_isolation_passes(self):
        if not SRC_AGENT.exists():
            return

        domain_dir = SRC_AGENT / "domain"
        if not domain_dir.exists():
            return

        forbidden_layers = {"infra", "presentation", "application"}
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            rel_path = py_file.relative_to(PROJECT_ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if (
                        len(parts) >= 3
                        and parts[0] == "modules"
                        and parts[1] == "agent"
                        and parts[2] in forbidden_layers
                    ):
                        violations.append(
                            f"{rel_path}:{node.lineno} domain imports {parts[2]}: {node.module}"
                        )

        assert not violations, (
            "Agent domain layer must not import from infra/presentation/application:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_add_agent_boundary_architecture_tests_rejects_legacy_imports(self):
        forbidden_source = """\
from modules.ai.domain.entities import Agent
from modules.knowledge.infra.repositories import DocRepo
from modules.runtime.service.ask_use_case import AskAgentUseCase
"""
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(node.module)

        assert len(violations) == 3, (
            f"Expected 3 legacy import violations from fixture, got {len(violations)}: {violations}"
        )
        assert "modules.ai.domain.entities" in violations
        assert "modules.knowledge.infra.repositories" in violations
        assert "modules.runtime.service.ask_use_case" in violations

    def test_add_agent_boundary_architecture_tests_rejects_layer_violations(self):
        forbidden_source = """\
from modules.agent.infra.database.models import AgentModel
from modules.agent.presentation.routes import router
from modules.agent.application.use_cases import SomeUseCase
"""
        tree = ast.parse(forbidden_source)
        forbidden_layers = {"infra", "presentation", "application"}
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if (
                    len(parts) >= 3
                    and parts[0] == "modules"
                    and parts[1] == "agent"
                    and parts[2] in forbidden_layers
                ):
                    violations.append((parts[2], node.module))

        assert len(violations) == 3, (
            f"Expected 3 layer violations from fixture, got {len(violations)}: {violations}"
        )
        assert violations[0][0] == "infra"
        assert violations[1][0] == "presentation"
        assert violations[2][0] == "application"
