"""Characterization test: detect legacy cross-module adapters still in use.

Known defects (initially RED — shrinks as hardening fixes each):
- MeteringUsageRecorder class still exists and is imported by ask_job_worker.py
- ObservabilityTraceRecorder class still exists and is imported by ask_job_worker.py

Corrective spec: 002
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_ADAPTER_IMPORTS: set[tuple[str, str]] = set()

KNOWN_ADAPTER_CLASSES: set[str] = set()


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestCharacterizationToolWiring:
    def test_no_new_legacy_adapter_imports(self):
        new_imports: list[tuple[str, str]] = []
        src_dir = PROJECT_ROOT / "src"
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            text = py_file.read_text(encoding="utf-8")
            for target, _ in KNOWN_ADAPTER_IMPORTS:
                if target == _relative_posix(py_file):
                    continue
                if "metering_usage_recorder" in text and "import" in text:
                    rel = _relative_posix(py_file)
                    for adapter_name in ("metering_usage_recorder", "observability_trace_recorder"):
                        if adapter_name in text and rel not in {x[0] for x in KNOWN_ADAPTER_IMPORTS}:
                            new_imports.append((rel, adapter_name))
        known_files = {x[0] for x in KNOWN_ADAPTER_IMPORTS}
        unknown_files = {x[0] for x in new_imports} - known_files
        assert not unknown_files, (
            f"New legacy adapter imports found: {unknown_files}"
        )

    def test_known_adapter_files_exist(self):
        for rel_path in KNOWN_ADAPTER_CLASSES:
            full_path = PROJECT_ROOT / rel_path
            assert full_path.exists(), (
                f"Known adapter file no longer exists: {rel_path}"
            )

    def test_no_adapter_usage_in_new_files(self):
        adapter_names = {"MeteringUsageRecorder", "ObservabilityTraceRecorder"}
        known_dirs = {
            "src/modules/agent",
        }
        new_usages: list[str] = []
        src_dir = PROJECT_ROOT / "src"
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            rel = _relative_posix(py_file)
            if any(rel.startswith(k) for k in known_dirs):
                continue
            text = py_file.read_text(encoding="utf-8")
            for name in adapter_names:
                if name in text:
                    new_usages.append(f"{rel}: {name}")
        assert not new_usages, (
            f"Legacy adapter usage in new locations: {new_usages}"
        )
