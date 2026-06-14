import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ARCH = Path(__file__).resolve().parent
SRC_WORKERS = PROJECT_ROOT / "src" / "workers"
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
WORKER_LOCATIONS_FILE = TESTS_ARCH / "test_worker_locations.py"
ALLOWLIST_FILE = TESTS_ARCH / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}


class TestAddWorkerLocationArchitectureTests:
    def test_add_worker_location_architecture_tests(self):
        assert WORKER_LOCATIONS_FILE.is_file(), (
            f"test_worker_locations.py must exist at {WORKER_LOCATIONS_FILE}"
        )

        source = WORKER_LOCATIONS_FILE.read_text(encoding="utf-8")
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
            "test_worker_locations.py must use the ast module for import analysis, not regex"
        )

        uses_ast_parse = "ast.parse" in source or "ast.walk" in source
        assert uses_ast_parse, (
            "test_worker_locations.py must use ast.parse/ast.walk for static analysis"
        )

        assert ALLOWLIST_FILE.is_file(), (
            f"legacy_import_allowlist.yaml must exist at {ALLOWLIST_FILE}"
        )

        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries") or []
        assert len(entries) > 0, "Allowlist must have at least one entry during migration"

        worker_entries = [e for e in entries if e.get("scope") == "worker_locations"]
        assert len(worker_entries) > 0, (
            "Allowlist must have entries with scope 'worker_locations' "
            "for known worker location violations"
        )

        required_fields = {"file", "target_module", "removal_spec", "scope"}
        for i, entry in enumerate(worker_entries):
            missing = required_fields - set(entry.keys())
            assert not missing, (
                f"Worker locations allowlist entry {i} missing fields: {missing}"
            )
            assert entry["file"].startswith("src/workers/"), (
                f"worker_locations entry must reference src/workers/ file: {entry['file']}"
            )
            assert entry.get("removal_spec"), (
                f"worker_locations entry missing removal_spec: {entry['file']}"
            )

    def test_add_worker_location_architecture_tests_rejects_forbidden(self):
        forbidden_source = """\
from modules.runtime.infra.ask_job_worker import AskJobWorker
from modules.metering.infra.models import UsageEventModel

class MyConcreteWorker:
    pass
"""
        tree = ast.parse(forbidden_source)

        internal_layers = {"domain", "infra", "application", "service", "presentation"}
        violations = []
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

        assert len(violations) == 2, (
            f"Expected 2 module internal import violations in fixture, got {len(violations)}: {violations}"
        )
        assert violations[0][0] == "runtime"
        assert violations[1][0] == "metering"

        worker_classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if "worker" in node.name.lower():
                    worker_classes.append(node.name)

        assert len(worker_classes) == 1, (
            f"Expected 1 worker class in fixture, got {len(worker_classes)}: {worker_classes}"
        )
        assert "MyConcreteWorker" in worker_classes
