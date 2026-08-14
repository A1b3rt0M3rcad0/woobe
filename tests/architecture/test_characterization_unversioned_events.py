"""Characterization test: detect unversioned event_type assignments in modules.

Known defects (initially RED — shrinks as hardening fixes each):
- billing: plan.created, customer.created, subscription.created
- core: project.created, api_key.created
- identity: user.created, workspace.created
- observability: trace.created, trace_event.created

Corrective spec: 003
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_UNVERSIONED: dict[str, list[str]] = {}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _find_event_type_assignments(file_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    results: list[str] = []
    for line in source.splitlines():
        m = re.search(r'event_type\s*=\s*["\']([^"\']+)["\']', line)
        if m:
            results.append(m.group(1))
        m2 = re.search(r'event_type=(["\'])([^"\']+)\1', line)
        if m2:
            results.append(m2.group(2))
    return results


class TestCharacterizationUnversionedEvents:
    def test_no_new_unversioned_events(self):
        new_unversioned: dict[str, list[str]] = {}
        modules = [
            "billing", "core", "identity", "metering", "observability", "agent"
        ]
        for mod in modules:
            mod_dir = PROJECT_ROOT / "src" / "modules" / mod / "application" / "use_cases"
            if not mod_dir.exists():
                continue
            for py_file in mod_dir.rglob("*.py"):
                if "__pycache__" in py_file.parts:
                    continue
                rel = _relative_posix(py_file)
                known = KNOWN_UNVERSIONED.get(rel, [])
                found = [e for e in _find_event_type_assignments(py_file) if ".v" not in e]
                unknown = [e for e in found if e not in known]
                if unknown:
                    new_unversioned[rel] = unknown
        assert not new_unversioned, (
            f"New unversioned events found:\n{new_unversioned}"
        )

    def test_known_unversioned_files_exist(self):
        for rel_path in KNOWN_UNVERSIONED:
            full_path = PROJECT_ROOT / rel_path
            assert full_path.exists(), (
                f"Known unversioned file no longer exists: {rel_path}"
            )
