from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import NetworkBudgetExceeded
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor


class _CancelAlreadyRequestedStore:
    def __init__(self) -> None:
        self.cancel_running_calls = 0

    async def is_cancel_requested(self, _execution_id):
        return True

    async def cancel_running_invocations(self, _execution_id):
        self.cancel_running_calls += 1


def _processor(store) -> NetworkExecutionProcessor:
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store
    return processor


@pytest.mark.asyncio
async def test_normal_completion_already_won_before_cancel_check_is_not_rewritten() -> None:
    store = _CancelAlreadyRequestedStore()
    processor = _processor(store)
    execution_id = uuid4()

    async def completed():
        return "completed-result"

    result = await processor._execute_with_cancellation(execution_id, completed())

    assert result == "completed-result"
    assert store.cancel_running_calls == 0


@pytest.mark.asyncio
async def test_timeout_already_won_before_cancel_check_is_not_rewritten_as_cancelled() -> None:
    store = _CancelAlreadyRequestedStore()
    processor = _processor(store)
    execution_id = uuid4()

    async def timed_out():
        raise NetworkBudgetExceeded(
            "Network execution timeout exceeded",
            code="network_timeout_exceeded",
        )

    with pytest.raises(NetworkBudgetExceeded) as exc_info:
        await processor._execute_with_cancellation(execution_id, timed_out())

    assert exc_info.value.code == "network_timeout_exceeded"
    assert store.cancel_running_calls == 0


@pytest.mark.asyncio
async def test_failure_already_won_before_cancel_check_remains_the_authoritative_failure() -> None:
    store = _CancelAlreadyRequestedStore()
    processor = _processor(store)
    execution_id = uuid4()

    async def failed():
        raise RuntimeError("provider failed first")

    with pytest.raises(RuntimeError, match="provider failed first"):
        await processor._execute_with_cancellation(execution_id, failed())

    assert store.cancel_running_calls == 0
