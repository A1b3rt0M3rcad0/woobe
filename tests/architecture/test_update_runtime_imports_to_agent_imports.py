"""Architecture tests for spec 045 — update runtime imports to agent imports."""
import ast
import pathlib
import warnings

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"


def _load_allowlist():
    with open(ALLOWLIST_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("entries", [])


def test_update_runtime_imports_to_agent_imports_success():
    """Verify agent module has zero imports from modules.runtime."""
    agent_dir = ROOT / "src" / "modules" / "agent"
    violations = []

    for py_file in agent_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "modules.runtime" in node.module:
                    rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
                    violations.append(f"{rel}: {node.module}")

    assert violations == [], (
        f"Agent module still imports from modules.runtime: {violations}"
    )


def test_update_runtime_imports_to_agent_imports_rejects_forbidden_dependency():
    """Verify no unlisted cross-module import from agent to runtime exists."""
    allowlist = _load_allowlist()
    allowed_files = {
        entry["file"]
        for entry in allowlist
        if entry.get("target_module") == "runtime"
    }

    agent_dir = ROOT / "src" / "modules" / "agent"
    violations = []

    for py_file in agent_dir.rglob("*.py"):
        rel_path = str(py_file.relative_to(ROOT)).replace("\\", "/")
        if rel_path in allowed_files:
            continue

        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "modules.runtime" in node.module:
                    violations.append(f"{rel_path}: {node.module}")

    assert violations == [], (
        f"Unlisted runtime imports in agent module: {violations}"
    )


def test_update_runtime_imports_to_agent_imports_keeps_legacy_compatibility():
    """Verify runtime shims still delegate correctly to agent."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)

        from modules.runtime.domain import entities as rt_entities
        assert hasattr(rt_entities, "Session")
        assert hasattr(rt_entities, "Message")
        assert hasattr(rt_entities, "AskJob")

        from modules.runtime.infra import repositories as rt_repos
        assert hasattr(rt_repos, "SQLAlchemySessionRepository")
        assert hasattr(rt_repos, "SQLAlchemyMessageRepository")
        assert hasattr(rt_repos, "SQLAlchemyAskJobRepository")

        from modules.runtime.presentation import routes as rt_routes
        assert hasattr(rt_routes, "router")

        from modules.runtime.infra import ask_job_worker as rt_worker
        assert hasattr(rt_worker, "AskJobWorker")
