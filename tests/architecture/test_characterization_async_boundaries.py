"""Characterization test: detect missing await on async outbox.write() calls.

Known defects (initially RED — shrinks as hardening fixes each):
- ask_use_case.py: 5 synchronous outbox.write() calls without await
- ask_agent_stream_service.py: 4 synchronous outbox.write() calls without await

Corrective spec: 001
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_VIOLATIONS: dict[str, list[int]] = {}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _find_sync_outbox_write(file_path: Path) -> list[int]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    lines: list[int] = []
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if "outbox.write(" in stripped and "await" not in stripped:
            lines.append(i)
    return lines


class TestCharacterizationAsyncBoundaries:
    def test_no_new_missing_await_on_outbox_write(self):
        new_violations: dict[str, list[int]] = {}
        src_dir = PROJECT_ROOT / "src"
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            rel = _relative_posix(py_file)
            known = KNOWN_VIOLATIONS.get(rel, [])
            found = _find_sync_outbox_write(py_file)
            unknown = [ln for ln in found if ln not in known]
            if unknown:
                new_violations[rel] = unknown
        assert not new_violations, (
            f"New missing await on outbox.write() found:\n{new_violations}"
        )

    def test_known_violation_sources_exist(self):
        for rel_path in KNOWN_VIOLATIONS:
            full_path = PROJECT_ROOT / rel_path
            assert full_path.exists(), (
                f"Known violation file no longer exists: {rel_path}"
            )
