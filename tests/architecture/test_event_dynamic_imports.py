"""Guards for event-driven-module-communication: detect dynamic cross-module imports.

Ensures that modules do not use importlib.import_module to access another module's
domain entities, enums, or repositories.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules"

CROSS_MODULE_DYNAMIC_PATTERNS: list[tuple[str, str, str]] = [
    ("metering", "domain.entities", "modules.metering.domain.entities"),
    ("metering", "domain.enums", "modules.metering.domain.enums"),
    ("metering", "infra.database.repositories", "modules.metering.infra.database.repositories"),
    ("observability", "domain.entities", "modules.observability.domain.entities"),
    ("observability", "domain.enums", "modules.observability.domain.enums"),
    ("observability", "infra.database.repositories", "modules.observability.infra.database.repositories"),
]

KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    ("packages/woobe-core/src/modules/agent/infra/adapters/metering_usage_recorder.py", "modules.metering.domain.entities"),
    ("packages/woobe-core/src/modules/agent/infra/adapters/metering_usage_recorder.py", "modules.metering.domain.enums"),
    ("packages/woobe-core/src/modules/agent/infra/adapters/metering_usage_recorder.py", "modules.metering.infra.database.repositories"),
    ("packages/woobe-core/src/modules/agent/infra/adapters/observability_trace_recorder.py", "modules.observability.domain.entities"),
    ("packages/woobe-core/src/modules/agent/infra/adapters/observability_trace_recorder.py", "modules.observability.domain.enums"),
    ("packages/woobe-core/src/modules/agent/infra/adapters/observability_trace_recorder.py", "modules.observability.infra.database.repositories"),
}


def _find_importlib_imports(file_path: Path) -> list[tuple[int, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    results: list[tuple[int, str]] = []
    for i, line in enumerate(source.splitlines(), 1):
        if "importlib.import_module" in line:
            match = re.search(r'import_module\(\s*["\']([^"\']+)["\']', line)
            if match:
                results.append((i, match.group(1)))
    return results


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestEventDynamicCrossModuleImports:
    def test_no_new_dynamic_cross_module_imports(self):
        violations: list[tuple[str, str]] = []
        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            for py_file in module_dir.rglob("*.py"):
                if not py_file.is_file():
                    continue
                for _, import_target in _find_importlib_imports(py_file):
                    for _, _, path_pattern in CROSS_MODULE_DYNAMIC_PATTERNS:
                        if path_pattern in import_target:
                            key = (_relative_posix(py_file), import_target)
                            if key not in KNOWN_VIOLATIONS:
                                violations.append(key)

        assert not violations, f"New/unknown dynamic cross-module imports: {violations}"

    def test_known_violation_sources_unchanged(self):
        current_files_with_violations: set[str] = set()
        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            for py_file in module_dir.rglob("*.py"):
                if not py_file.is_file():
                    continue
                for _, import_target in _find_importlib_imports(py_file):
                    for _, _, path_pattern in CROSS_MODULE_DYNAMIC_PATTERNS:
                        if path_pattern in import_target:
                            current_files_with_violations.add(_relative_posix(py_file))

        known_files = {file_path for file_path, _ in KNOWN_VIOLATIONS}
        unknown_files = current_files_with_violations - known_files
        assert not unknown_files, (
            f"New files with dynamic cross-module imports: {unknown_files}"
        )
