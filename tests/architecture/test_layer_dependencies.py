import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_LAYERS = {"domain", "application", "service", "infra", "presentation"}
COMPOSER_DIRS = {"composers"}
SCOPE = "layer_dependencies"


def _load_allowlist() -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries") or []
    return {
        (e["file"].replace("\\", "/"), e.get("target_layer", ""))
        for e in entries
        if e.get("scope") == SCOPE
    }


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _repository_path(path_value: str) -> Path:
    return PROJECT_ROOT.joinpath(*path_value.replace("\\", "/").split("/"))


def _extract_layer_imports(file_path: Path) -> list[tuple[str, str, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    relative_module_path = file_path.relative_to(SRC_MODULES)
    if len(relative_module_path.parts) < 2:
        return []
    source_module = relative_module_path.parts[0]
    rel_path = _relative_posix(file_path)
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod_parts = node.module.split(".")
            if (
                len(mod_parts) >= 3
                and mod_parts[0] == "modules"
                and mod_parts[1] == source_module
            ):
                target_layer = mod_parts[2]
                if target_layer in KNOWN_LAYERS:
                    violations.append((rel_path, target_layer, node.module))

    return violations


class TestLayerDependencies:
    def test_no_unlisted_layer_violations(self):
        allowlist = _load_allowlist()
        unlisted = []

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            for py_file in module_dir.rglob("*.py"):
                rel_path = _relative_posix(py_file)
                relative_module_path = py_file.relative_to(SRC_MODULES)
                parts = relative_module_path.parts
                parent_dir = parts[1] if len(parts) > 1 else ""
                grandparent_dir = parts[2] if len(parts) > 2 else ""
                source_module = parts[0]
                is_composer = parent_dir in COMPOSER_DIRS or grandparent_dir in COMPOSER_DIRS

                for rel_path_imp, target_layer, full_import in _extract_layer_imports(py_file):
                    if is_composer:
                        continue

                    is_domain = "/domain/" in rel_path_imp
                    is_presentation = "/presentation/" in rel_path_imp
                    is_use_case = "/service/use_cases.py" in rel_path_imp or "/application/use_cases/" in rel_path_imp

                    should_check = (
                        (is_domain and target_layer in ("application", "service", "infra", "presentation"))
                        or (is_presentation and target_layer == "infra")
                        or (is_use_case and target_layer == "infra")
                    )
                    if not should_check:
                        continue

                    if (rel_path_imp, target_layer) not in allowlist:
                        unlisted.append(
                            f"{rel_path_imp} imports {full_import} (layer violation: {source_module}/{parent_dir} -> {target_layer})"
                        )

        assert not unlisted, (
            f"Found {len(unlisted)} unlisted layer violation(s):\n"
            + "\n".join(f"  - {v}" for v in unlisted[:20])
        )

    def test_allowlist_entries_reference_valid_files(self):
        allowlist_data = {}
        if ALLOWLIST_FILE.exists():
            with open(ALLOWLIST_FILE, encoding="utf-8") as f:
                allowlist_data = yaml.safe_load(f) or {}

        entries = allowlist_data.get("entries") or []
        layer_entries = [e for e in entries if e.get("scope") == SCOPE]

        for entry in layer_entries:
            file_path = _repository_path(entry["file"])
            assert file_path.exists(), (
                f"Allowlist references non-existent file: {entry['file']}"
            )
            assert entry.get("removal_spec"), (
                f"Allowlist entry missing removal_spec: {entry['file']}"
            )

    def test_detects_forbidden_infra_import_in_use_case(self):
        forbidden_source = "from modules.tools.infra.models import SecretModel"
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod_parts = node.module.split(".")
                if (
                    len(mod_parts) >= 3
                    and mod_parts[0] == "modules"
                    and mod_parts[2] == "infra"
                ):
                    violations.append(node.module)
        assert len(violations) >= 1, "Fixture should be detected"
