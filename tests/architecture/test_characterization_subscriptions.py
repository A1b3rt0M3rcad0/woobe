"""Characterization test: detect subscription catalog gaps and self-subscriptions.

Known defects (initially RED — shrinks as hardening fixes each):
- agent.# self-subscription still active in inbox consumer

Corrective spec: 003
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_SELF_SUBSCRIBERS: set[str] = {
    "src/modules/agent/infra/workers/inbox_consumer.py",
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
        new_self_sub: set[str] = set()
        src_dir = PROJECT_ROOT / "src"
        for py_file in src_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            if "inbox_consumer" not in py_file.name:
                continue
            text = py_file.read_text(encoding="utf-8")
            rel = _relative_posix(py_file)
            if '"agent.#"' in text or "'agent.#'" in text:
                if rel not in KNOWN_SELF_SUBSCRIBERS:
                    new_self_sub.add(rel)
        assert not new_self_sub, (
            f"New self-subscribers found: {new_self_sub}"
        )

    def test_known_self_subscriber_exists(self):
        for rel_path in KNOWN_SELF_SUBSCRIBERS:
            full_path = PROJECT_ROOT / rel_path
            assert full_path.exists(), (
                f"Known self-subscriber file no longer exists: {rel_path}"
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
