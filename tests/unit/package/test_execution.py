from types import SimpleNamespace
import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.package.application.execution import (
    DependencyWait,
    ExecutePackageOperation,
)
from modules.package.domain.errors import PackageError


@pytest.mark.asyncio
async def test_long_native_phase_renews_lease_and_stops_when_fenced():
    operation, work, repository = setup_work()
    started, stopped = asyncio.Event(), asyncio.Event()

    async def execute(work, phase):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def heartbeat(identifier, token):
        await started.wait()
        assert identifier == operation.id and token == operation.lease_token
        raise PackageError("PACKAGE_OPERATION_FENCED", "Lease belongs to another worker")

    repository.heartbeat = AsyncMock(side_effect=heartbeat)
    executor = SimpleNamespace(execute_phase=AsyncMock(side_effect=execute))
    assert await asyncio.wait_for(ExecutePackageOperation(repository, executor,
        heartbeat_seconds=0.001).run_once(), timeout=1)
    assert stopped.is_set() and not work.receipts
    assert all(call.args[2] != "failed" for call in repository.advance.await_args_list)


def setup_work():
    operation = SimpleNamespace(id=uuid4(), lease_token=uuid4(), state="resolving")
    work = SimpleNamespace(
        operation=operation,
        plan={
            "effects": [
                {"key": "model:first", "state": "materializing"},
                {"key": "verification", "state": "verifying"},
            ]
        },
        receipts={},
    )
    repository = SimpleNamespace(
        claim=AsyncMock(return_value=operation),
        load_work=AsyncMock(return_value=work),
        advance=AsyncMock(),
    )

    async def advance(identifier, lease, state, **changes):
        assert identifier == operation.id and lease == operation.lease_token
        operation.state = state
        return operation

    repository.advance.side_effect = advance
    return operation, work, repository


@pytest.mark.asyncio
async def test_recovery_reuses_committed_phase_receipts_and_only_then_succeeds():
    operation, work, repository = setup_work()
    work.receipts["model:first"] = {"data": {"id": "installed"}}
    executor = SimpleNamespace(execute_phase=AsyncMock())

    async def execute(work, phase):
        work.receipts[phase["key"]] = {"data": {"verified": True}}

    executor.execute_phase.side_effect = execute
    assert await ExecutePackageOperation(repository, executor).run_once()
    assert executor.execute_phase.await_count == 1
    assert operation.state == "succeeded"


@pytest.mark.asyncio
async def test_missing_native_receipt_cannot_repeat_effect_or_claim_success():
    operation, work, repository = setup_work()
    executor = SimpleNamespace(execute_phase=AsyncMock(return_value=None))
    await ExecutePackageOperation(repository, executor).run_once()
    assert executor.execute_phase.await_count == 1
    assert operation.state == "failed"
    assert repository.advance.await_args.kwargs["diagnostics"] == [
        {"code": "PACKAGE_NATIVE_RECEIPT_MISSING"}
    ]


@pytest.mark.asyncio
async def test_dependency_wait_retains_pending_phase_and_never_claims_ready():
    operation, work, repository = setup_work()
    dependency = {
        "kind": "VectorSnapshot",
        "state": "building",
        "resource_id": "vector",
    }
    executor = SimpleNamespace(
        execute_phase=AsyncMock(return_value=DependencyWait([dependency]))
    )
    await ExecutePackageOperation(repository, executor).run_once()
    assert operation.state == "waiting_dependency" and not work.receipts
    assert repository.advance.await_args.kwargs == {"dependencies": [dependency]}


@pytest.mark.asyncio
async def test_cancellation_retains_committed_inventory_without_owner_deletion():
    operation, work, repository = setup_work()
    operation.state = "cancelling"
    work.receipts["model:first"] = {"data": {"id": "shared-model"}}
    executor = SimpleNamespace(execute_phase=AsyncMock())
    await ExecutePackageOperation(repository, executor).run_once()
    executor.execute_phase.assert_not_awaited()
    assert operation.state == "cancelled" and work.receipts["model:first"]


@pytest.mark.asyncio
async def test_fenced_worker_cannot_publish_failure_or_more_effects():
    operation, work, repository = setup_work()
    repository.load_work.side_effect = PackageError(
        "PACKAGE_OPERATION_FENCED", "Cancelled"
    )
    executor = SimpleNamespace(execute_phase=AsyncMock())
    await ExecutePackageOperation(repository, executor).run_once()
    executor.execute_phase.assert_not_awaited()
    repository.advance.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_exception_echo_never_reaches_operation_diagnostics():
    operation, work, repository = setup_work()
    executor = SimpleNamespace(
        execute_phase=AsyncMock(side_effect=RuntimeError("private-provider-value"))
    )
    await ExecutePackageOperation(repository, executor).run_once()
    assert repository.advance.await_args.kwargs["diagnostics"] == [
        {"code": "PACKAGE_NATIVE_PHASE_FAILED"}
    ]
