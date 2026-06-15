import ast
import importlib
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
ALLOWLIST_FILE = PROJECT_ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"

MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]

MODULES_WITH_REGISTRY = ["agent", "billing", "identity", "metering", "observability", "tools"]


def _load_allowlist(scope: str) -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (e["file"].replace("/", "\\").replace("\\", "/"), e["target_module"])
        for e in entries
        if e.get("scope") == scope
    }


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestPublicAPIEntrypoints:
    def test_each_module_init_exposes_routes(self):
        for mod_name in MODULES:
            mod = importlib.import_module(f"modules.{mod_name}")
            assert hasattr(mod, "routes"), (
                f"modules.{mod_name}.__init__ must expose 'routes'"
            )

    def test_each_module_init_exposes_registry(self):
        for mod_name in MODULES_WITH_REGISTRY:
            mod = importlib.import_module(f"modules.{mod_name}")
            assert hasattr(mod, "registry"), (
                f"modules.{mod_name}.__init__ must expose 'registry'"
            )

    def test_each_module_init_has_all_list(self):
        for mod_name in MODULES:
            mod = importlib.import_module(f"modules.{mod_name}")
            assert hasattr(mod, "__all__"), (
                f"modules.{mod_name}.__init__ must define __all__"
            )
            assert "routes" in mod.__all__, (
                f"modules.{mod_name}.__all__ must include 'routes'"
            )
        for mod_name in MODULES_WITH_REGISTRY:
            mod = importlib.import_module(f"modules.{mod_name}")
            assert "registry" in mod.__all__, (
                f"modules.{mod_name}.__all__ must include 'registry'"
            )

    def test_external_code_does_not_access_internal_module_paths(self):
        allowlist = _load_allowlist("module_boundaries")
        violations = []

        for py_file in SRC_MODULES.rglob("*.py"):
            rel = _relative_posix(py_file)
            parts = rel.split("/")
            if len(parts) < 4 or parts[0] != "src" or parts[1] != "modules":
                continue
            source_module = parts[2]
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                mod_parts = node.module.split(".")
                if len(mod_parts) >= 2 and mod_parts[0] == "modules":
                    target_module = mod_parts[1]
                    if target_module != source_module and target_module in MODULES:
                        if len(mod_parts) >= 4:
                            access_depth = "/".join(mod_parts[2:])
                            if (rel, target_module) not in allowlist:
                                violations.append(
                                    f"{rel}: accesses {target_module}.{access_depth}"
                                )

        assert not violations, (
            f"External access to internal module paths ({len(violations)} violation(s)):\n"
            + "\n".join(f"  - {v}" for v in violations[:20])
        )

    def test_no_imports_of_dead_legacy_modules(self):
        legacy_modules = {"ai", "knowledge", "runtime"}
        violations = []

        for py_file in SRC_MODULES.rglob("*.py"):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 2 and parts[0] == "modules" and parts[1] in legacy_modules:
                        violations.append(f"{rel}: imports legacy module {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 2 and parts[0] == "modules" and parts[1] in legacy_modules:
                            violations.append(f"{rel}: imports legacy module {alias.name}")

        assert not violations, (
            f"Legacy module imports found ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations[:20])
        )
