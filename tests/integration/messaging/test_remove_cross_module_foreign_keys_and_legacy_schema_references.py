"""Integration tests for spec 099 — remove cross-module FKs and legacy schema refs.

Validates that no model files contain ForeignKey to another module's schema,
and no legacy ai/runtime schema references remain.
"""
from __future__ import annotations

import pathlib
import re


MODELS_PATHS = [
    pathlib.Path(f"src/modules/{m}/infra/database/models.py")
    for m in ["agent", "billing", "core", "identity", "metering", "observability", "tools"]
]


def _find_cross_module_fks(filepath: pathlib.Path) -> list[str]:
    """Find ForeignKey references to schemas outside the owning module."""
    if not filepath.is_file():
        return []
    module_name = filepath.parts[2]
    text = filepath.read_text(encoding="utf-8")
    # Match ForeignKey("schema.table_ref")
    matches = re.findall(r'ForeignKey\("([^"]+)"\)', text)
    cross_module = []
    for m in matches:
        schema = m.split(".")[0]
        if schema != module_name and schema not in ("ai", "knowledge", "runtime"):
            cross_module.append(f"{filepath.name}: ForeignKey({m!r})")
    return cross_module


def _find_legacy_schema_refs(filepath: pathlib.Path) -> list[str]:
    """Find references to legacy ai/knowledge/runtime schemas."""
    if not filepath.is_file():
        return []
    text = filepath.read_text(encoding="utf-8")
    refs = []
    for schema in ("ai", "knowledge", "runtime"):
        pattern = re.compile(
            rf'(?:(?:ForeignKey|schema)\s*=\s*["\']{schema}\.|["\']{schema}\.\w+)'
        )
        for m in pattern.finditer(text):
            refs.append(f"Legacy schema {schema!r} in {filepath.name}: {m.group()}")
    return refs


def test_no_cross_module_fks_in_agent():
    refs = _find_cross_module_fks(MODELS_PATHS[0])
    assert not refs, f"Cross-module FKs in agent: {refs}"


def test_no_cross_module_fks_in_billing():
    refs = _find_cross_module_fks(MODELS_PATHS[1])
    assert not refs, f"Cross-module FKs in billing: {refs}"


def test_no_cross_module_fks_in_core():
    refs = _find_cross_module_fks(MODELS_PATHS[2])
    assert not refs, f"Cross-module FKs in core: {refs}"


def test_no_cross_module_fks_in_identity():
    refs = _find_cross_module_fks(MODELS_PATHS[3])
    assert not refs, f"Cross-module FKs in identity: {refs}"


def test_no_cross_module_fks_in_metering():
    refs = _find_cross_module_fks(MODELS_PATHS[4])
    assert not refs, f"Cross-module FKs in metering: {refs}"


def test_no_cross_module_fks_in_observability():
    refs = _find_cross_module_fks(MODELS_PATHS[5])
    assert not refs, f"Cross-module FKs in observability: {refs}"


def test_no_cross_module_fks_in_tools():
    refs = _find_cross_module_fks(MODELS_PATHS[6])
    assert not refs, f"Cross-module FKs in tools: {refs}"


def test_no_legacy_schema_references():
    all_refs = []
    for p in MODELS_PATHS:
        if p.is_file():
            all_refs.extend(_find_legacy_schema_refs(p))
    assert not all_refs, f"Legacy schema refs: {all_refs}"
