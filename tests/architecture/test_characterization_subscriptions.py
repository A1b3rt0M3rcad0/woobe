"""Characterize routing-key coverage in worker-host consumers."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONSUMERS = (
    PROJECT_ROOT / "packages" / "woobe-workers" / "src"
    / "woobe_workers" / "consumers"
)

KNOWN_SELF_SUBSCRIBERS: set[str] = {
    "packages/woobe-workers/src/woobe_workers/consumers/core/inbox_consumer.py",
    "packages/woobe-workers/src/woobe_workers/consumers/identity/inbox_consumer.py",
}

ALL_SUBSCRIBED_EVENT_TYPES: set[str] = {
    "agent.execution.requested.v1",
    "agent.execution.started.v1",
    "agent.execution.llm_completed.v1",
    "agent.execution.tool_completed.v1",
    "agent.execution.fallback_triggered.v1",
    "agent.execution.completed.v1",
    "agent.execution.failed.v1",
}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestCharacterizationSubscriptions:
    def test_no_new_self_subscribers(self):
        violations: list[str] = []
        for py_file in CONSUMERS.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                if (".#" in line or '"#' in line) and "ROUTING_KEYS" in line:
                    rel = _relative_posix(py_file)
                    if rel not in KNOWN_SELF_SUBSCRIBERS:
                        violations.append(f"{rel}: {line.strip()}")
        assert not violations, (
            f"New self-subscription glob patterns found:\n{violations}"
        )

    def test_metering_has_all_agent_execution_events(self):
        consumer_path = CONSUMERS / "metering" / "inbox_consumer.py"
        assert consumer_path.is_file()
        text = consumer_path.read_text(encoding="utf-8")
        found = {key for key in ALL_SUBSCRIBED_EVENT_TYPES if key in text}
        assert found == ALL_SUBSCRIBED_EVENT_TYPES, (
            f"Metering consumer missing keys: {ALL_SUBSCRIBED_EVENT_TYPES - found}"
        )

    def test_observability_has_all_agent_execution_events(self):
        consumer_path = CONSUMERS / "observability" / "inbox_consumer.py"
        assert consumer_path.is_file()
        text = consumer_path.read_text(encoding="utf-8")
        found = {key for key in ALL_SUBSCRIBED_EVENT_TYPES if key in text}
        assert found == ALL_SUBSCRIBED_EVENT_TYPES, (
            f"Observability consumer missing keys: {ALL_SUBSCRIBED_EVENT_TYPES - found}"
        )
