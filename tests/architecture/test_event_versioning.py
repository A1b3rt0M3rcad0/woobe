"""Guards for event-driven-module-communication: detect unversioned events.

Ensures that integration events follow the format <producer>.<capability>.<fact>.vN.
Detects event_type strings in use cases and domain events that lack version suffix.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"

ALLOWED_UNVERSIONED_EVENTS: set[str] = {
    "tools.tool.created",
    "tools.tool.updated",
    "tools.tool.status_changed",
    "tools.secret.created",
    "tool_call",
    "llm_call",
    "info",
}

ALLOWED_UNVERSIONED_FILES: set[str] = {
    "packages/woobe-core/src/modules/agent/infra/adapters/observability_trace_recorder.py",
    "packages/woobe-core/src/modules/agent/application/use_cases/ask_use_case.py",
    "packages/woobe-core/src/modules/agent/application/use_cases/ask_agent_stream_service.py",
    "packages/woobe-core/src/modules/agent/application/use_cases/ai_use_cases.py",
    "packages/woobe-core/src/modules/agent/application/use_cases/knowledge_use_cases.py",
    "packages/woobe-core/src/modules/agent/application/use_cases/runtime_use_cases.py",
    "packages/woobe-core/src/modules/agent/application/use_cases/tools_use_cases.py",
    "packages/woobe-core/src/modules/agent/infra/adapters/metering_usage_recorder.py",
}


def _find_event_type_assignments(file_path: Path) -> list[tuple[int, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    results: list[tuple[int, str]] = []
    for i, line in enumerate(source.splitlines(), 1):
        m = re.search(r'event_type\s*=\s*["\']([^"\']+)["\']', line)
        if m:
            results.append((i, m.group(1)))
        m2 = re.search(r'event_type=(["\'])([^"\']+)\1', line)
        if m2:
            results.append((i, m2.group(2)))
    return results


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestEventVersioning:
    def test_domain_events_have_version_suffix(self):
        agent_domain = SRC_MODULES / "agent" / "domain" / "events.py"
        assert agent_domain.exists(), "Agent domain events file not found"

        for line_no, event_type in _find_event_type_assignments(agent_domain):
            if event_type in ALLOWED_UNVERSIONED_EVENTS:
                continue
            assert ".v" in event_type, (
                f"Domain event without version suffix at line {line_no}: {event_type}"
            )

    def test_use_case_events_should_not_add_new_unversioned(self):
        agent_dir = SRC_MODULES / "agent" / "application" / "use_cases"
        new_unversioned: list[tuple[str, int, str]] = []

        for py_file in agent_dir.rglob("*.py"):
            if not py_file.is_file():
                continue
            rel = _relative_posix(py_file).replace("\\", "/")
            for line_no, event_type in _find_event_type_assignments(py_file):
                if event_type in ALLOWED_UNVERSIONED_EVENTS:
                    continue
                if ".v" not in event_type and rel not in ALLOWED_UNVERSIONED_FILES:
                    new_unversioned.append((rel, line_no, event_type))

        assert not new_unversioned, (
            f"New unversioned event types (add to ALLOWED_UNVERSIONED_FILES if intentional): {new_unversioned}"
        )
