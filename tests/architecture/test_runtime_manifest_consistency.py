"""Tests for spec 009 — runtime and manifest consistency.

Validates that:
- runtime.md exists and contains status entries for all specs 000-109.
- All allowlist entries have required fields: path, scope, removal_spec.
- The manifest defines all expected specs.
- No physical move spec precedes the discovery specs (010-019).
"""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUITE_ROOT = PROJECT_ROOT / "specs" / "module-architecture-standardization"
RUNTIME_MD = SUITE_ROOT / "execution" / "runtime.md"
MANIFEST_MD = SUITE_ROOT / "MANIFEST.md"
ALLOWLIST_FILE = PROJECT_ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"
FK_ALLOWLIST_FILE = (
    PROJECT_ROOT / "tests" / "architecture" / "legacy_database_fk_allowlist.yaml"
)


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestRuntimeManifestConsistency:
    def test_runtime_md_exists(self):
        assert RUNTIME_MD.is_file(), (
            f"runtime.md not found at {_relative_posix(RUNTIME_MD)}"
        )

    def test_runtime_has_all_spec_entries(self):
        assert RUNTIME_MD.is_file()
        content = RUNTIME_MD.read_text(encoding="utf-8")

        spec_ids = set()
        for line in content.splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 6 and line.startswith("| "):
                first = parts[1].strip()
                if first.isdigit():
                    spec_ids.add(int(first))

        expected = set(range(0, 110))
        missing = expected - spec_ids
        assert not missing, (
            f"runtime.md missing status entries for specs: {sorted(missing)}"
        )

    def test_runtime_has_próxima_spec_recommended(self):
        assert RUNTIME_MD.is_file()
        content = RUNTIME_MD.read_text(encoding="utf-8")
        assert "Próxima spec recomendada" in content, (
            "runtime.md must have 'Próxima spec recomendada' section"
        )

    def test_allowlist_entries_have_required_fields(self):
        for allowlist_path in [ALLOWLIST_FILE, FK_ALLOWLIST_FILE]:
            if not allowlist_path.is_file():
                continue
            with open(allowlist_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            entries = data.get("entries") or []
            for i, entry in enumerate(entries):
                assert "removal_spec" in entry, (
                    f"Allowlist entry {i} missing 'removal_spec' in {_relative_posix(allowlist_path)}"
                )
                if allowlist_path == FK_ALLOWLIST_FILE:
                    assert "source_module" in entry, (
                        f"FK allowlist entry {i} missing 'source_module' "
                        f"in {_relative_posix(allowlist_path)}"
                    )
                else:
                    assert "file" in entry, (
                        f"Import allowlist entry {i} missing 'file' "
                        f"in {_relative_posix(allowlist_path)}"
                    )

    def test_manifest_defines_specs_000_to_109(self):
        assert MANIFEST_MD.is_file(), (
            f"MANIFEST.md not found at {_relative_posix(MANIFEST_MD)}"
        )
        content = MANIFEST_MD.read_text(encoding="utf-8")

        manifest_ids = set()
        for line in content.splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 2:
                first = parts[1].strip()
                if first.isdigit() and len(first) == 3:
                    manifest_ids.add(int(first))

        expected = set(range(0, 110))
        missing = expected - manifest_ids
        assert not missing, (
            f"MANIFEST.md missing entries for specs: {sorted(missing)}"
        )

    def test_no_physical_move_spec_before_discovery(self):
        assert MANIFEST_MD.is_file()
        content = MANIFEST_MD.read_text(encoding="utf-8")

        physical_types = {"refactor", "cleanup", "messaging", "worker", "test", "validation"}

        for line in content.splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 5:
                spec_str = parts[1].strip()
                spec_type = parts[3].strip().lower()
                if spec_str.isdigit():
                    spec_num = int(spec_str)
                    if spec_type in physical_types:
                        assert spec_num >= 20, (
                            f"Spec {spec_num} is type '{spec_type}' but is numbered "
                            f"before discovery specs (010-019)"
                        )
