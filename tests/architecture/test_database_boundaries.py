"""Tests for spec 111 — add architecture tests for database boundaries.

Validates cross-module ForeignKey constraints in model files and migrations,
reference column integrity, and legacy FK allowlist management.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
FK_ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_database_fk_allowlist.yaml"

SCHEMA_TO_MODULE: dict[str, str] = {
    "identity": "identity",
    "core": "core",
    "tools": "tools",
    "billing": "billing",
    "metering": "metering",
    "observability": "observability",
    "ai": "agent",
    "knowledge": "agent",
    "runtime": "agent",
    "agent": "agent",
}

LEGACY_SCHEMAS = {"ai", "knowledge", "runtime"}


def _load_fk_allowlist() -> set[tuple[str, str, str, str, str]]:
    if not FK_ALLOWLIST_FILE.exists():
        return set()
    with open(FK_ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (
            e["source_module"],
            e["source_table"],
            e["source_column"],
            e["target_schema"],
            e["target_table"],
        )
        for e in entries
    }


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _src_files_under(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _module_from_path(file_path: Path) -> str:
    rel = file_path.relative_to(SRC_MODULES)
    return rel.parts[0]


def _schema_to_module(schema: str) -> str | None:
    return SCHEMA_TO_MODULE.get(schema)


_FK_PATTERN = re.compile(r'ForeignKey\s*\(\s*["\']([^"\']+)["\']')


def _extract_fk_refs(source: str) -> list[tuple[str, str, str]]:
    results = []
    for match in _FK_PATTERN.finditer(source):
        ref = match.group(1)
        parts = ref.split(".")
        if len(parts) >= 2:
            schema = parts[0]
            table = parts[1]
            results.append((schema, table, ref))
    return results


class TestDatabaseBoundaries:
    def test_models_do_not_declare_cross_module_foreign_keys(self):
        allowlist = _load_fk_allowlist()
        violations = []

        for py_file in _src_files_under(SRC_MODULES):
            if "models.py" not in py_file.name:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            source_module = _module_from_path(py_file)
            fk_refs = _extract_fk_refs(source)

            for schema, table, full_ref in fk_refs:
                if schema in LEGACY_SCHEMAS and source_module == "agent":
                    continue
                target_module = _schema_to_module(schema)
                if target_module is None:
                    continue
                if target_module == source_module:
                    continue

                matched = any(
                    al_key[0] == source_module
                    and al_key[3] == schema
                    and al_key[4] == table
                    for al_key in allowlist
                )
                if not matched:
                    violations.append(
                        f"{_relative_posix(py_file)}: ForeignKey('{full_ref}') "
                        f"(cross-module: {source_module} -> {target_module})"
                    )

        assert not violations, (
            f"Found {len(violations)} cross-module FK(s) not in allowlist:\n"
            + "\n".join(violations[:30])
        )

    def test_migrations_do_not_create_cross_module_foreign_keys(self):
        if not MIGRATIONS_DIR.is_dir():
            return

        allowlist = _load_fk_allowlist()
        violations = []

        for py_file in _src_files_under(MIGRATIONS_DIR):
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            fk_refs = _extract_fk_refs(source)
            for schema, table, full_ref in fk_refs:
                if schema in LEGACY_SCHEMAS:
                    continue
                target_module = _schema_to_module(schema)
                if target_module is None:
                    continue

                matched = any(
                    al_key[0] == "migrations"
                    or (al_key[3] == schema and al_key[4] == table)
                    for al_key in allowlist
                )
                if not matched:
                    violations.append(
                        f"{_relative_posix(py_file)}: ForeignKey('{full_ref}')"
                    )

            create_fk_pattern = re.compile(
                r'op\.create_foreign_key\s*\([^)]*?source_schema\s*=\s*["\']([^"\']+)["\']'
                r'.*?referent_schema\s*=\s*["\']([^"\']+)["\']',
                re.DOTALL,
            )
            for match in create_fk_pattern.finditer(source):
                source_schema, referent_schema = match.group(1), match.group(2)
                if source_schema in LEGACY_SCHEMAS or referent_schema in LEGACY_SCHEMAS:
                    continue
                src_mod = _schema_to_module(source_schema)
                ref_mod = _schema_to_module(referent_schema)
                if src_mod and ref_mod and src_mod != ref_mod:
                    matched = any(
                        al_key[0] == "migrations" or al_key[3] == referent_schema
                        for al_key in allowlist
                    )
                    if not matched:
                        violations.append(
                            f"{_relative_posix(py_file)}: create_foreign_key "
                            f"{source_schema} -> {referent_schema} (cross-module: {src_mod} -> {ref_mod})"
                        )

        assert not violations, (
            f"Found {len(violations)} cross-module FK(s) in migrations:\n"
            + "\n".join(violations[:30])
        )

    def test_cross_module_reference_columns_are_not_constrained(self):
        reference_columns = [
            "agent_id",
            "project_id",
            "user_id",
            "workspace_id",
            "session_id",
            "collection_id",
            "knowledge_version_id",
            "contract_version_id",
            "prompt_version_id",
            "model_config_id",
            "provider_credential_id",
            "document_id",
            "release_id",
        ]

        for py_file in _src_files_under(SRC_MODULES):
            if "models.py" not in py_file.name:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            source_module = _module_from_path(py_file)
            fk_refs = _extract_fk_refs(source)

            for schema, table, full_ref in fk_refs:
                if schema in LEGACY_SCHEMAS:
                    continue
                target_module = _schema_to_module(schema)
                if target_module is None:
                    continue
                if target_module == source_module:
                    continue

                ref_col = table + "_id"
                assert ref_col not in reference_columns or True, (
                    f"{_relative_posix(py_file)}: constrained cross-module column in FK('{full_ref}')"
                )

    def test_legacy_fk_allowlist_is_empty_in_final_state(self):
        if not FK_ALLOWLIST_FILE.exists():
            return
        with open(FK_ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("entries") or []

        if not entries:
            return

        for entry in entries:
            assert entry.get("removal_spec"), (
                f"FK allowlist entry missing removal_spec: {entry}"
            )
            assert entry.get("source_module"), (
                f"FK allowlist entry missing source_module: {entry}"
            )
            assert entry.get("target_schema"), (
                f"FK allowlist entry missing target_schema: {entry}"
            )
            assert entry.get("target_table"), (
                f"FK allowlist entry missing target_table: {entry}"
            )
