"""Guards for event-driven-module-communication: detect self-subscriptions.

Ensures that modules do not use generic self-subscriptions like "agent.#" or
"billing.#" without explicit justification. Agent self-subscription was
removed in spec 006 (tool events use Outbox to publish, never self-consume).
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules"

KNOWN_SELF_SUBSCRIPTIONS: set[str] = {"billing", "core", "identity"}


def _find_routing_key_definitions(file_path: Path) -> list[tuple[int, str, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    results: list[tuple[int, str, str]] = []
    for i, line in enumerate(source.splitlines(), 1):
        match = re.search(r'["\'](\w+)\.#["\']', line)
        if match and ("ROUTING_KEYS" in line or "routing_keys" in line):
            results.append((i, match.group(1), line.strip()))
    return results


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestEventSelfSubscriptions:
    def test_no_new_self_subscriptions(self):
        violations: set[str] = set()

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            module_name = module_dir.name
            for py_file in module_dir.rglob("*.py"):
                if not py_file.is_file():
                    continue
                for _, prefix, _ in _find_routing_key_definitions(py_file):
                    if (
                        prefix == module_name
                        and module_name not in KNOWN_SELF_SUBSCRIPTIONS
                        and module_name != "agent"
                    ):
                        violations.add(module_name)

        assert not violations, f"Unexpected self-subscriptions detected: {violations}"

    def test_agent_no_self_subscription(self):
        agent_dir = SRC_MODULES / "agent"
        for py_file in agent_dir.rglob("*.py"):
            if not py_file.is_file():
                continue
            for line_no, prefix, _ in _find_routing_key_definitions(py_file):
                assert prefix != "agent", (
                    f"Agent self-subscription (agent.#) found in {_relative_posix(py_file)}:{line_no}. "
                    "Agent self-subscription was removed in spec 006."
                )
