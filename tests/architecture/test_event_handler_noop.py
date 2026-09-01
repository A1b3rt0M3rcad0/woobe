"""Guards for event-driven-module-communication: detect no-op inbox handlers.

Ensures that inbox handlers in each module implement real use cases instead of
only logging "Routing event" or "No handler registered".
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules"

KNOWN_NOOP_HANDLERS: set[str] = {"billing", "core", "identity", "metering", "observability"}

HANDLER_FILES_TO_CHECK: list[str] = [
    "billing/infra/messaging/inbox_handlers.py",
    "core/infra/messaging/inbox_handlers.py",
    "identity/infra/messaging/inbox_handlers.py",
    "metering/infra/messaging/inbox_handlers.py",
    "observability/infra/messaging/inbox_handlers.py",
]


class TestEventHandlerNoop:
    def test_no_new_noop_handlers(self):
        current_noop_modules: set[str] = set()

        for rel_path in HANDLER_FILES_TO_CHECK:
            file_path = SRC_MODULES / rel_path
            if not file_path.exists():
                continue
            source = file_path.read_text(encoding="utf-8")

            if '"No handler registered' in source:
                current_noop_modules.add(rel_path.split("/")[0])

        unknown_noop = current_noop_modules - KNOWN_NOOP_HANDLERS
        assert not unknown_noop, f"New no-op modules detected: {unknown_noop}"

    def test_agent_no_self_consumption_handlers(self):
        file_path = SRC_MODULES / "agent" / "infra" / "messaging" / "inbox_handlers.py"
        assert file_path.exists(), "Agent inbox handlers file not found"
        source = file_path.read_text(encoding="utf-8")
        assert "AGENT_TOOL_EVENT_HANDLERS" not in source, (
            "Agent must not register self-consumption handlers for its own events"
        )
