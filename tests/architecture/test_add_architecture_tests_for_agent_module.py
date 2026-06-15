"""Tests for spec 114 — add architecture tests for agent module.

Validates agent module internal architecture: layer isolation, directory structure,
cross-module import restrictions, UoW scope, and layer dependency rules.
"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_AGENT = PROJECT_ROOT / "src" / "modules" / "agent"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in (PROJECT_ROOT / "src" / "modules").iterdir()
    if d.is_dir() and not d.name.startswith("_")
}

LEGACY_MODULES = {"ai", "knowledge", "runtime"}

AGENT_REQUIRED_LAYERS = {"domain", "application", "infra", "presentation"}

LAYER_FORBIDDEN = {
    "domain": {"infra", "presentation", "application"},
    "application": {"infra", "presentation"},
}


def _load_allowlist(scope: str) -> set[str]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        e["file"].replace("\\", "/")
        for e in entries
        if e.get("scope") == scope
    }


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _src_files_under(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


class TestAddArchitectureTestsForAgentModule:
    """Agent module architecture tests for spec 114."""

    def test_add_architecture_tests_for_agent_module(self):
        assert SRC_AGENT.is_dir(), "agent module directory must exist"

        violations = []

        present_layers = {
            d.name
            for d in SRC_AGENT.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        }
        missing = AGENT_REQUIRED_LAYERS - present_layers
        assert not missing, (
            f"Agent module missing required layers: {missing}"
        )

        forbid_targets = KNOWN_MODULES - {"agent", *LEGACY_MODULES}
        for py_file in _src_files_under(SRC_AGENT):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = str(node.module).split(".")
                    if len(parts) >= 2 and parts[0] == "modules":
                        target = parts[1]
                        if target in forbid_targets:
                            allowlist = _load_allowlist("module_boundaries")
                            if rel not in allowlist and rel.replace("\\", "/") not in allowlist:
                                violations.append(
                                    f"{rel} imports forbidden module: {target}"
                                )

        violations.sort()
        assert not violations, (
            f"Agent imports {len(violations)} non-agent non-legacy module(s):\n"
            + "\n".join(violations)
        )

    def test_agent_domain_layer_isolation(self):
        domain_dir = SRC_AGENT / "domain"
        if not domain_dir.is_dir():
            return

        violations = []
        forbidden = LAYER_FORBIDDEN["domain"]

        for py_file in _src_files_under(domain_dir):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = str(node.module).split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] == "agent":
                        layer = parts[2]
                        if layer in forbidden:
                            violations.append(
                                f"{rel} domain imports {layer}: {node.module}"
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 3 and parts[0] == "modules" and parts[1] == "agent":
                            layer = parts[2]
                            if layer in forbidden:
                                violations.append(
                                    f"{rel} domain imports {layer}: {alias.name}"
                                )

        assert not violations, (
            f"Agent domain layer has {len(violations)} forbidden import(s):\n"
            + "\n".join(violations)
        )

    def test_agent_application_layer_isolation(self):
        app_dir = SRC_AGENT / "application"
        if not app_dir.is_dir():
            return

        orchestration_files = {"ask_use_case.py", "ask_agent_stream_service.py"}
        violations = []
        forbidden = LAYER_FORBIDDEN["application"]

        for py_file in _src_files_under(app_dir):
            if "composers" in py_file.parts:
                continue
            if py_file.name in orchestration_files:
                continue

            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = str(node.module).split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] == "agent":
                        layer = parts[2]
                        if layer in forbidden:
                            violations.append(
                                f"{rel} application imports {layer}: {node.module}"
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 3 and parts[0] == "modules" and parts[1] == "agent":
                            layer = parts[2]
                            if layer in forbidden:
                                violations.append(
                                    f"{rel} application imports {layer}: {alias.name}"
                                )

        assert not violations, (
            f"Agent application layer has {len(violations)} forbidden import(s):\n"
            + "\n".join(violations)
        )

    def test_agent_infra_layer_structure(self):
        infra_dir = SRC_AGENT / "infra"
        if not infra_dir.is_dir():
            return

        required_dirs = {"database", "messaging", "workers", "llm"}
        present = {
            d.name for d in infra_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        }

        missing = required_dirs - present
        assert not missing, (
            f"Agent infra layer missing required directories: {missing}"
        )

    def test_agent_does_not_import_legacy_modules(self):
        allowlist = _load_allowlist("module_boundaries")
        violations = []

        for py_file in _src_files_under(SRC_AGENT):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = str(node.module).split(".")
                    if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                        if rel not in allowlist and rel.replace("\\", "/") not in allowlist:
                            violations.append(
                                f"{rel} imports legacy module {parts[1]}: {node.module}"
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                            if rel not in allowlist and rel.replace("\\", "/") not in allowlist:
                                violations.append(
                                    f"{rel} imports legacy module {parts[1]}: {alias.name}"
                                )

        assert not violations, (
            f"Agent imports {len(violations)} legacy module(s) without allowlist:\n"
            + "\n".join(violations)
        )

    def test_agent_unit_of_work_does_not_span_multiple_modules(self):
        uow_file = SRC_AGENT / "infra" / "database" / "unit_of_work.py"
        if not uow_file.is_file():
            return

        source = uow_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(uow_file))

        module_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = str(node.module).split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] != "agent":
                    module_imports.add(parts[1])

        assert not module_imports, (
            f"Agent UoW imports from non-agent modules: {module_imports}"
        )

    def test_agent_presentation_layer_structure(self):
        pres_dir = SRC_AGENT / "presentation"
        if not pres_dir.is_dir():
            return

        required_files = {"routes.py", "schemas.py"}
        for fname in required_files:
            fpath = pres_dir / fname
            assert fpath.is_file(), (
                f"Agent presentation layer missing {fname}"
            )

        controllers_dir = pres_dir / "controllers"
        assert controllers_dir.is_dir(), (
            "Agent presentation layer missing controllers directory"
        )


class TestAddArchitectureTestsForAgentModuleRejectsForbidden:
    """Regression: forbidden agent module patterns are detected."""

    def test_detects_agent_domain_importing_infra(self):
        code = "from modules.agent.infra.database.models import AgentModel\n"
        tree = ast.parse(code)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = str(node.module).split(".")
                if len(parts) >= 3 and parts[0:3] == ["modules", "agent", "infra"]:
                    found = True
        assert found

    def test_detects_agent_importing_non_agent_module(self):
        code = "from modules.billing.infra.repositories import BillingRepository\n"
        tree = ast.parse(code)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = str(node.module).split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] != "agent":
                    found = True
        assert found
