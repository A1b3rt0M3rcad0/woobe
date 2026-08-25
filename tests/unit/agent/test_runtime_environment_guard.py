from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.infra.adapters.runtime_environment_guard import (
    build_agent_runtime_environment_guard,
)


class _EnvironmentReader:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def assert_enabled(self, **kwargs) -> None:
        self.calls.append(dict(kwargs))


class _Transactions:
    def __init__(self) -> None:
        self.environment = _EnvironmentReader()
        self.read_calls = 0
        self.write_calls = 0

    async def read(self, operation):
        self.read_calls += 1
        repositories = SimpleNamespace(environment=self.environment)
        return await operation(repositories, None)

    async def run(self, operation):
        self.write_calls += 1
        raise AssertionError("environment preflight must not open a write transaction")


@pytest.mark.asyncio
async def test_runtime_environment_guard_uses_short_read_boundary() -> None:
    transactions = _Transactions()
    guard = build_agent_runtime_environment_guard(transactions)
    agent_id = uuid4()
    project_id = uuid4()

    await guard(agent_id, project_id, "staging")

    assert transactions.read_calls == 1
    assert transactions.write_calls == 0
    assert transactions.environment.calls == [
        {
            "agent_id": agent_id,
            "project_id": project_id,
            "environment": "staging",
        }
    ]
