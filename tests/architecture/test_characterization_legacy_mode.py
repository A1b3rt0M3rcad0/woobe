"""Characterization test: detect legacy mode and direct-write patterns.

Known defects (initially RED — shrinks as hardening fixes each):
- _legacy_mode flag in ask_use_case.py
- _do_save_assistant_message method in ask_use_case.py

Corrective spec: 001
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_LEGACY_PATTERNS: dict[str, list[str]] = {
    "src/modules/agent/application/use_cases/ask_use_case.py": [
        "_legacy_mode",
        "_do_save_assistant_message",
    ],
    "src/modules/agent/infra/adapters/metering_usage_recorder.py": [
        "MeteringUsageRecorder",
    ],
    "src/modules/agent/infra/adapters/observability_trace_recorder.py": [
        "ObservabilityTraceRecorder",
    ],
    "src/modules/agent/infra/workers/ask_job_worker.py": [
        "MeteringUsageRecorder",
        "ObservabilityTraceRecorder",
    ],
}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestCharacterizationLegacyMode:
    def test_no_new_legacy_mode_patterns(self):
        new_patterns: dict[str, list[str]] = {}
        patterns_to_scan = [
            "_legacy_mode",
            "_do_save_assistant_message",
            "MeteringUsageRecorder",
            "ObservabilityTraceRecorder",
        ]
        src_dir = PROJECT_ROOT / "src"
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            rel = _relative_posix(py_file)
            known = KNOWN_LEGACY_PATTERNS.get(rel, [])
            text = py_file.read_text(encoding="utf-8")
            for pat in patterns_to_scan:
                if pat in text and pat not in known:
                    if rel not in new_patterns:
                        new_patterns[rel] = []
                    new_patterns[rel].append(pat)
        assert not new_patterns, (
            f"New legacy patterns found:\n{new_patterns}"
        )

    def test_known_legacy_files_exist(self):
        for rel_path in KNOWN_LEGACY_PATTERNS:
            full_path = PROJECT_ROOT / rel_path
            assert full_path.exists(), (
                f"Known legacy file no longer exists: {rel_path}"
            )
