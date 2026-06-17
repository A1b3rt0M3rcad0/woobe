"""Characterization test: verify zero legacy cross-module adapter patterns remain.

Corrective spec: 002 (resolved — no legacy patterns remain).
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_LEGACY_PATTERNS: dict[str, list[str]] = {}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestCharacterizationLegacyMode:
    def test_no_legacy_cross_module_adapter_patterns(self):
        patterns_to_scan = [
            "MeteringUsageRecorder",
            "ObservabilityTraceRecorder",
            "_legacy_mode",
        ]
        found_patterns: dict[str, list[str]] = {}
        src_dir = PROJECT_ROOT / "src"
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            rel = _relative_posix(py_file)
            text = py_file.read_text(encoding="utf-8")
            for pat in patterns_to_scan:
                if pat in text:
                    if rel not in found_patterns:
                        found_patterns[rel] = []
                    found_patterns[rel].append(pat)
        assert not found_patterns, (
            f"Legacy cross-module adapter patterns still present:\n{found_patterns}"
        )
