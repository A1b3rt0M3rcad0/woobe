import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_WORKERS = PROJECT_ROOT / "src" / "workers"
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}


def _load_allowlist(scope: str) -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (e["file"].replace("\\", "/"), e["target_module"])
        for e in entries
        if e.get("scope") == scope
    }


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _extract_module_internal_imports(file_path: Path) -> list[tuple[str, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []
    internal_layers = {"domain", "infra", "application", "service", "presentation"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if (
                len(parts) >= 3
                and parts[0] == "modules"
                and parts[1] in KNOWN_MODULES
                and parts[2] in internal_layers
            ):
                violations.append((parts[1], node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if (
                    len(parts) >= 3
                    and parts[0] == "modules"
                    and parts[1] in KNOWN_MODULES
                    and parts[2] in internal_layers
                ):
                    violations.append((parts[1], alias.name))
    return violations


class TestWorkerLocations:
    def test_no_unlisted_module_imports_in_root_workers(self):
        if not SRC_WORKERS.exists():
            return

        allowlist = _load_allowlist("worker_locations")
        unlisted = []

        for py_file in SRC_WORKERS.rglob("*.py"):
            imports = _extract_module_internal_imports(py_file)
            if imports:
                rel_path = _relative_posix(py_file)
                for target_mod, full_import in imports:
                    if (rel_path, target_mod) not in allowlist:
                        unlisted.append(
                            f"{rel_path} imports {full_import} (module internal)"
                        )

        assert not unlisted, (
            "Root workers must not import module internals (unlisted):\n"
            + "\n".join(f"  - {v}" for v in unlisted)
        )

    def test_concrete_workers_belong_to_modules(self):
        if not SRC_MODULES.exists():
            return

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            workers_dir = module_dir / "infra" / "workers"
            if workers_dir.exists():
                for py_file in workers_dir.rglob("*.py"):
                    if py_file.name.startswith("_"):
                        continue
                    try:
                        source = py_file.read_text(encoding="utf-8")
                        tree = ast.parse(source, filename=str(py_file))
                    except (SyntaxError, UnicodeDecodeError):
                        continue
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            if "worker" in node.name.lower():
                                rel_path = _relative_posix(py_file)
                                assert rel_path.startswith("src/modules/"), (
                                    f"Worker {node.name} in {rel_path} is not under src/modules/"
                                )

    def test_allowlist_entries_have_removal_spec(self):
        if not ALLOWLIST_FILE.exists():
            return
        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("entries") or []
        worker_entries = [e for e in entries if e.get("scope") == "worker_locations"]
        for entry in worker_entries:
            assert entry.get("removal_spec"), (
                f"Worker allowlist entry missing removal_spec: {entry['file']}"
            )

    def test_detects_forbidden_module_import_in_workers(self):
        forbidden_source = """\
from modules.runtime.infra.ask_job_worker import AskJobWorker
from modules.ai.domain.entities import Agent
"""
        tree = ast.parse(forbidden_source)
        violations = []
        internal_layers = {"domain", "infra", "application", "service", "presentation"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if (
                    len(parts) >= 3
                    and parts[0] == "modules"
                    and parts[1] in KNOWN_MODULES
                    and parts[2] in internal_layers
                ):
                    violations.append((parts[1], node.module))

        assert len(violations) == 2, (
            f"Expected 2 violations from fixture, got {len(violations)}"
        )
        assert violations[0][0] == "runtime"
        assert violations[1][0] == "ai"
