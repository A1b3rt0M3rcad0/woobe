"""Durable phase orchestration; native owners execute and receipt each effect."""

from dataclasses import dataclass
import asyncio
from contextlib import suppress
from typing import Protocol

from modules.package.domain.errors import PackageError
from modules.package.domain.operations import OperationState


@dataclass(frozen=True)
class DependencyWait:
    dependencies: list[dict]


class PackageExecutionRepository(Protocol):
    async def claim(self, *, project_id=None): ...
    async def load_work(self, operation_id, lease_token): ...
    async def advance(self, operation_id, lease_token, target, **changes): ...
    async def heartbeat(self, operation_id, lease_token): ...


class NativePackageExecutor(Protocol):
    async def execute_phase(self, work, phase): ...


class ExecutePackageOperation:
    def __init__(
        self,
        repository: PackageExecutionRepository,
        executor: NativePackageExecutor,
        *,
        heartbeat_seconds: float | None = None,
    ):
        self._repository, self._executor = repository, executor
        self._heartbeat_seconds = heartbeat_seconds

    async def _execute_phase(self, work, phase):
        if self._heartbeat_seconds is None:
            return await self._executor.execute_phase(work, phase)

        async def renew():
            while True:
                await asyncio.sleep(self._heartbeat_seconds)
                await self._repository.heartbeat(
                    work.operation.id, work.operation.lease_token
                )

        execution = asyncio.create_task(self._executor.execute_phase(work, phase))
        heartbeat = asyncio.create_task(renew())
        try:
            completed, _ = await asyncio.wait(
                {execution, heartbeat}, return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat in completed:
                await heartbeat
            return await execution
        finally:
            for task in (execution, heartbeat):
                task.cancel()
            for task in (execution, heartbeat):
                with suppress(asyncio.CancelledError):
                    await task

    async def run_once(self, *, project_id=None):
        operation = await self._repository.claim(project_id=project_id)
        if operation is None:
            return False
        lease = operation.lease_token
        try:
            while True:
                work = await self._repository.load_work(operation.id, lease)
                if work.operation.state == OperationState.CANCELLING:
                    # Cancellation retains shared/activated resources and committed
                    # receipts. No owner deletion is an incidental cancellation.
                    await self._repository.advance(
                        operation.id, lease, OperationState.CANCELLED
                    )
                    return True
                pending = [
                    effect
                    for effect in work.plan["effects"]
                    if effect["key"] not in work.receipts
                ]
                if not pending:
                    if work.operation.state != OperationState.VERIFYING:
                        raise PackageError(
                            "PACKAGE_VERIFICATION_MISSING",
                            "Native verification has not completed",
                        )
                    await self._repository.advance(
                        operation.id, lease, OperationState.SUCCEEDED
                    )
                    return True
                phase = pending[0]
                target = OperationState(phase["state"])
                if (
                    work.operation.state == OperationState.RESOLVING
                    and target == OperationState.VERIFYING
                ):
                    await self._repository.advance(
                        operation.id, lease, OperationState.MATERIALIZING
                    )
                await self._repository.advance(
                    operation.id, lease, target, phase=phase["key"]
                )
                result = await self._execute_phase(work, phase)
                if isinstance(result, DependencyWait):
                    await self._repository.advance(
                        operation.id,
                        lease,
                        OperationState.WAITING_DEPENDENCY,
                        dependencies=result.dependencies,
                    )
                    return True
                recorded = await self._repository.load_work(operation.id, lease)
                if phase["key"] not in recorded.receipts:
                    raise PackageError(
                        "PACKAGE_NATIVE_RECEIPT_MISSING",
                        "Native phase did not commit its transaction-bound receipt",
                    )
        except PackageError as exc:
            if exc.code == "PACKAGE_OPERATION_FENCED":
                # A cancellation or newer worker owns the operation now.
                return True
            try:
                await self._repository.advance(
                    operation.id,
                    lease,
                    OperationState.FAILED,
                    diagnostics=[{"code": exc.code}],
                )
            except PackageError as fenced:
                if fenced.code != "PACKAGE_OPERATION_FENCED":
                    raise
            return True
        except Exception:
            # Never persist or log native exception messages: they may contain
            # credentials, document text or provider/MCP echoes.
            try:
                await self._repository.advance(
                    operation.id,
                    lease,
                    OperationState.FAILED,
                    diagnostics=[{"code": "PACKAGE_NATIVE_PHASE_FAILED"}],
                )
            except PackageError as fenced:
                if fenced.code != "PACKAGE_OPERATION_FENCED":
                    raise
            return True
