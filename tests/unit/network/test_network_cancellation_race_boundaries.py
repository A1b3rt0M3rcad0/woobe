from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import NetworkBudgetExceeded
from woobe_workers.consumers.network.execution_worker import NetworkExecutionProcessor


class _CancellationStore:
    def __init__(self) -> None:
        self.cancel_running_calls = 0

    async def is_cancel_requested(self, _execution_id) -> bool:
        return True

    async def cancel_running_invocations(self, _execution_id) -> None:
        self.cancel_running_calls += 1


@pytest.mark.asyncio
async def test_timeout_wins_when_execution_is_already_terminal_at_cancel_poll_boundary() -> None:
    store = _CancellationStore()
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store

    async def timed_out_execution():
        raise NetworkBudgetExceeded(
            "Network execution deadline exceeded",
            code="network_timeout",
        )

    with pytest.raises(NetworkBudgetExceeded) as exc_info:
        await processor._execute_with_cancellation(
            uuid4(),
            timed_out_execution(),
        )

    assert exc_info.value.code == "network_timeout"
    assert store.cancel_running_calls == 0
