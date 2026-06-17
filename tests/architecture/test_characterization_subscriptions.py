"""Characterization test: detect subscription catalog gaps and self-subscriptions.

Corrective spec: 003 (resolved — agent.# self-subscription removed).
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_SELF_SUBSCRIBERS: set[str] = {
    "src/modules/billing/infra/workers/inbox_consumer.py",
    "src/modules/core/infra/workers/inbox_consumer.py",
    "src/modules/identity/infra/workers/inbox_consumer.py",
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
        src_dir = PROJECT_ROOT / "src"
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            text = py_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                if ('.#' in line or '"#' in line) and "ROUTING_KEYS" in line:
                    rel = _relative_posix(py_file)
                    if rel not in KNOWN_SELF_SUBSCRIBERS:
                        violations.append(f"{rel}: {line.strip()}")
        assert not violations, (
            f"New self-subscription glob patterns found:\n{violations}"
        )

    def test_metering_has_all_agent_execution_events(self):
        consumer_path = PROJECT_ROOT / "src" / "modules" / "metering" / "infra" / "workers" / "inbox_consumer.py"
        if not consumer_path.exists():
            return
        text = consumer_path.read_text(encoding="utf-8")
        found = {key for key in ALL_SUBSCRIBED_EVENT_TYPES if key in text}
        assert found == ALL_SUBSCRIBED_EVENT_TYPES, (
            f"Metering consumer missing keys: {ALL_SUBSCRIBED_EVENT_TYPES - found}"
        )

    def test_observability_has_expected_agent_events(self):
        consumer_path = PROJECT_ROOT / "src" / "modules" / "observability" / "infra" / "workers" / "inbox_consumer.py"
        if not consumer_path.exists():
            return
        text = consumer_path.read_text(encoding="utf-8")
        expected = ALL_SUBSCRIBED_EVENT_TYPES - {"agent.execution.requested.v1"}
        found = {key for key in expected if key in text}
        assert found == expected, (
            f"Observability consumer missing keys: {expected - found}"
        )
