"""Tests for spec 008 — database ownership and no cross-module ForeignKeys.

Validates that:
- Every FK in models.py is classified as intra-module or cross-module.
- Cross-module FKs have corresponding allowlist entries.
- Legacy schema references (ai, knowledge, runtime) are flagged.
- Migration operations respect module boundaries.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules"
MIGRATIONS_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "migrations" / "versions"
FK_ALLOWLIST_FILE = (
    PROJECT_ROOT / "tests" / "architecture" / "legacy_database_fk_allowlist.yaml"
)

LEGACY_SCHEMAS = {"ai", "knowledge", "runtime"}

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

_FK_PATTERN = re.compile(r'ForeignKey\s*\(\s*["\']([^"\']+)["\']')


def _load_fk_allowlist() -> set[tuple[str, str, str, str, str]]:
    if not FK_ALLOWLIST_FILE.exists():
        return set()
    with open(FK_ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries") or []
    return {
        (
            e["source_module"],
            e.get("source_table", ""),
            e.get("source_column", ""),
            e["target_schema"],
            e["target_table"],
        )
        for e in entries
    }


def _module_from_path(file_path: Path) -> str:
    rel = file_path.relative_to(SRC_MODULES)
    return rel.parts[0]


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _schema_to_module(schema: str) -> str | None:
    return SCHEMA_TO_MODULE.get(schema)


def _extract_fk_refs(source: str) -> list[tuple[str, str, str]]:
    results = []
    for match in _FK_PATTERN.finditer(source):
        ref = match.group(1)
        parts = ref.split(".")
        if len(parts) >= 2:
            results.append((parts[0], parts[1], ref))
    return results


def _migration_fk_refs(source: str) -> list[tuple[str, str, str]]:
    # Inline ForeignKeys inherit their owning create_table schema. A reference
    # within that same module is not a cross-module dependency.
    owners: dict[str, set[str]] = {}
    for table in ast.walk(ast.parse(source)):
        if not isinstance(table, ast.Call) or not isinstance(table.func, ast.Attribute) or table.func.attr != "create_table":
            continue
        schema = next((keyword.value.value for keyword in table.keywords if keyword.arg == "schema" and isinstance(keyword.value, ast.Constant)), None)
        if not isinstance(schema, str):
            continue
        for node in ast.walk(table):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "ForeignKey" and node.args and isinstance(node.args[0], ast.Constant):
                owners.setdefault(node.args[0].value, set()).add(schema)
    return [(schema, table, ref) for schema, table, ref in _extract_fk_refs(source)
            if not owners.get(ref) or any(_schema_to_module(owner) != _schema_to_module(schema) for owner in owners[ref])]


def test_migration_inline_fk_classifier_preserves_cross_module_detection():
    source = "op.create_table('versions', sa.Column('skill_id', sa.ForeignKey('agent.skills.id')), sa.Column('project_id', sa.ForeignKey('core.projects.id')), schema='agent')"
    assert _migration_fk_refs(source) == [("core", "projects", "core.projects.id")]


class TestNoCrossModuleForeignKeys:
    def test_all_fks_classified_as_intra_or_cross(self):
        intra_count = 0
        cross_count = 0
        legacy_refs = []
        cross_unlisted = []
        allowlist = _load_fk_allowlist()

        for py_file in sorted(SRC_MODULES.rglob("*.py")):
            if "models.py" not in py_file.name:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            source_module = _module_from_path(py_file)
            for schema, table, full_ref in _extract_fk_refs(source):
                target_module = _schema_to_module(schema)
                if target_module is None:
                    continue

                if schema in LEGACY_SCHEMAS:
                    legacy_refs.append(
                        f"{_relative_posix(py_file)}: FK('{full_ref}') (legacy schema '{schema}')"
                    )
                    cross_count += 1
                    continue

                if target_module == source_module:
                    intra_count += 1
                else:
                    cross_count += 1
                    matched = any(
                        key[0] == source_module and key[3] == schema and key[4] == table
                        for key in allowlist
                    )
                    if not matched:
                        cross_unlisted.append(
                            f"{_relative_posix(py_file)}: FK('{full_ref}') "
                            f"({source_module} -> {schema}.{table})"
                        )

        total = intra_count + cross_count
        print(f"FK Inventory: {total} total ({intra_count} intra, {cross_count} cross)")
        print(f"Legacy schema refs: {len(legacy_refs)}")

        if legacy_refs:
            print("CRITICAL: Legacy schema references found:")
            for ref in legacy_refs:
                print(f"  - {ref}")

        assert not cross_unlisted, (
            f"Cross-module FKs without allowlist entry ({len(cross_unlisted)}):\n"
            + "\n".join(cross_unlisted[:20])
        )

    def test_legacy_schema_references_are_critical(self):
        critical_refs = []
        for py_file in SRC_MODULES.rglob("*.py"):
            if "models.py" not in py_file.name:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for schema, _, full_ref in _extract_fk_refs(source):
                if schema in LEGACY_SCHEMAS:
                    critical_refs.append(
                        f"{_relative_posix(py_file)}: FK('{full_ref}') "
                        f"(legacy schema '{schema}', must be migrated to 'agent')"
                    )

        if critical_refs:
            import warnings

            warnings.warn(
                f"Found {len(critical_refs)} critical legacy schema FK references:\n"
                + "\n".join(critical_refs)
            )

    def test_migrations_do_not_create_cross_module_fks(self):
        if not MIGRATIONS_DIR.is_dir():
            return

        allowlist = _load_fk_allowlist()
        violations = []

        for py_file in sorted(MIGRATIONS_DIR.rglob("*.py")):
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for schema, table, full_ref in _migration_fk_refs(source):
                if schema in LEGACY_SCHEMAS:
                    continue
                target_module = _schema_to_module(schema)
                if target_module is None:
                    continue
                matched = any(
                    key[0] == "migrations" or (key[3] == schema and key[4] == table)
                    for key in allowlist
                )
                if not matched:
                    violations.append(
                        f"{_relative_posix(py_file)}: FK('{full_ref}')"
                    )

            create_fk_pattern = re.compile(
                r"op\.create_foreign_key\s*\([^)]*?"
                r"source_schema\s*=\s*['\"]([^'\"]+)['\"]"
                r".*?"
                r"referent_schema\s*=\s*['\"]([^'\"]+)['\"]",
                re.DOTALL,
            )
            for match in create_fk_pattern.finditer(source):
                src_schema, ref_schema = match.group(1), match.group(2)
                if src_schema in LEGACY_SCHEMAS or ref_schema in LEGACY_SCHEMAS:
                    continue
                src_mod = _schema_to_module(src_schema)
                ref_mod = _schema_to_module(ref_schema)
                if src_mod and ref_mod and src_mod != ref_mod:
                    matched = any(
                        key[0] == "migrations" or key[3] == ref_schema
                        for key in allowlist
                    )
                    if not matched:
                        violations.append(
                            f"{_relative_posix(py_file)}: create_foreign_key "
                            f"{src_schema} -> {ref_schema} (cross-module)"
                        )

        assert not violations, (
            "Cross-module FK(s) in migrations not allowlisted:\n"
            + "\n".join(violations[:20])
        )
