import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_AGENT = CORE_SRC / "modules" / "agent"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

LEGACY_MODULES = {"ai", "knowledge", "runtime"}
RUNTIME_ORCHESTRATION_FILES = {
    "ask_use_case.py",
    "ask_agent_stream_service.py",
    "instrumented_execution_finalizer.py",
}


def _load_agent_allowlist() -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries") or []
    return {
        (e["file"].replace("\\", "/"), e["target_module"])
        for e in entries
        if e.get("scope") == "module_boundaries"
    }


LAYER_RULES = {
    "domain": {"infra", "presentation", "application"},
    "application": {"infra", "presentation"},
}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _extract_imports(file_path: Path) -> list[tuple[str, int]]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
    return imports


class TestAgentBoundaries:
    def test_agent_does_not_import_legacy_modules(self):
        if not SRC_AGENT.exists():
            return

        allowlist = _load_agent_allowlist()
        violations = []
        for py_file in SRC_AGENT.rglob("*.py"):
            imports = _extract_imports(py_file)
            rel_path = _relative_posix(py_file)
            for module_path, lineno in imports:
                parts = module_path.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    if (rel_path, parts[1]) not in allowlist:
                        violations.append(f"{rel_path}:{lineno} imports {module_path}")

        assert not violations, (
            "Agent module must not import from legacy modules (ai, knowledge, runtime):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_agent_domain_does_not_import_infra_or_presentation(self):
        if not SRC_AGENT.exists():
            return

        domain_dir = SRC_AGENT / "domain"
        if not domain_dir.exists():
            return

        violations = []
        forbidden_for_domain = LAYER_RULES["domain"]

        for py_file in domain_dir.rglob("*.py"):
            imports = _extract_imports(py_file)
            rel_path = _relative_posix(py_file)
            for module_path, lineno in imports:
                parts = module_path.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] == "agent":
                    layer = parts[2]
                    if layer in forbidden_for_domain:
                        violations.append(
                            f"{rel_path}:{lineno} domain imports {layer}: {module_path}"
                        )

        assert not violations, (
            "Agent domain layer must not import from infra/presentation/application:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_agent_application_does_not_import_infra_or_presentation(self):
        if not SRC_AGENT.exists():
            return

        app_dir = SRC_AGENT / "application"
        if not app_dir.exists():
            return

        violations = []
        forbidden_for_app = LAYER_RULES["application"]

        for py_file in app_dir.rglob("*.py"):
            if "composers" in py_file.parts:
                continue
            if py_file.name in RUNTIME_ORCHESTRATION_FILES:
                continue
            imports = _extract_imports(py_file)
            rel_path = _relative_posix(py_file)
            for module_path, lineno in imports:
                parts = module_path.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] == "agent":
                    layer = parts[2]
                    if layer in forbidden_for_app:
                        violations.append(
                            f"{rel_path}:{lineno} application imports {layer}: {module_path}"
                        )

        assert not violations, (
            "Agent application layer must not import from infra/presentation:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_detects_forbidden_legacy_import_in_agent(self):
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
            f"Expected 3 legacy import violations from fixture, got {len(violations)}"
        )

    def test_detects_forbidden_layer_violation_in_agent(self):
        forbidden_source = """\
from modules.agent.infra.database.models import AgentModel
from woobe_api.http.agent.routes import router
"""
        tree = ast.parse(forbidden_source)
        violations = []
        forbidden_for_domain = LAYER_RULES["domain"]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] == "agent":
                    layer = parts[2]
                    if layer in forbidden_for_domain:
                        violations.append(node.module)

        assert len(violations) == 2, (
            f"Expected 2 layer violations from fixture, got {len(violations)}"
        )

