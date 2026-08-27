from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import suppress
from typing import Any
from uuid import UUID

from aio_pika import IncomingMessage

from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.network.application.runtime import (
    NetworkBudgetExceeded,
    NetworkExecutionCancelled,
    NetworkExecutor,
)
from modules.network.application.runtime_failures import NetworkRuntimeFailure
from modules.network.infra.runtime.agent_invoker import ProjectRAIAgentInvoker
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from modules.network.infra.runtime.loader import NetworkRuntimeLoader
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.infra.config import Settings
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.inbox_consumer_base import BaseInboxConsumer, InboxRecord

logger = logging.getLogger(__name__)

_TERMINAL_EXECUTION_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "uncertain",
}


class NetworkExecutionProcessor:
    """Run a Network with Redis ownership and one terminal PostgreSQL write."""

    def __init__(
        self,
        *,
        loader: NetworkRuntimeLoader,
        store: RedisNetworkExecutionStore,
        finalizer: NetworkRuntimeFinalizer,
        settings: Settings,
        http_executor: HttpToolExecutor,
        lease_ttl_seconds: int,
        heartbeat_seconds: int,
        worker_id: str | None = None,
    ) -> None:
        self._loader = loader
        self._store = store
        self._finalizer = finalizer
        self._settings = settings
        self._lease_ttl_seconds = lease_ttl_seconds
        self._heartbeat_seconds = heartbeat_seconds
        self._worker_id = worker_id or f"network-worker-{os.getpid()}"
        self._agent_invoker = ProjectRAIAgentInvoker(settings, http_executor)

    async def process(self, execution_id: UUID) -> None:
        loaded = await self._loader.load(execution_id)
        if loaded is None:
            return
        execution = loaded.execution
        version = loaded.version
        if str(execution.status) in _TERMINAL_EXECUTION_STATUSES:
            return
        if version is None and not (
            execution.draft_revision is not None
            and execution.definition_snapshot
            and execution.resolved_bindings_snapshot
        ):
            await self._finalize_failure(
                execution_id,
                version,
                code="version_missing",
                detail="Pinned Network version not found",
                uncertain=False,
            )
            return

        await self._store.initialize(
            execution,
            ttl_seconds=max(self._lease_ttl_seconds * 10, 3600),
            agent_contexts=loaded.agent_contexts,
        )

        durable = await self._loader.load(execution_id)
        if durable is None:
            return
        durable_status = str(durable.execution.status)
        if durable_status == "cancelled":
            await self._store.request_cancel(execution_id)
            await self._store.mark_persisted(execution_id, status="cancelled")
            return
        if durable_status == "cancel_requested":
            await self._store.request_cancel(execution_id)
        elif durable_status in _TERMINAL_EXECUTION_STATUSES:
            await self._store.mark_persisted(execution_id, status=durable_status)
            return

        state = await self._store.snapshot(execution_id)
        if state.get("status") == "terminal_pending_persist":
            await self._resume_terminal(execution_id, version, state)
            return

        lease = await self._store.acquire_lease(
            execution_id,
            worker_id=self._worker_id,
            ttl_seconds=self._lease_ttl_seconds,
        )
        if lease is None:
            return

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat(execution_id, stop_heartbeat, lease_lost)
        )
        try:
            executor = NetworkExecutor(invoker=self._agent_invoker, store=self._store)
            result = await self._execute_with_cancellation(
                execution_id,
                executor.execute(execution, version),
            )
            if lease_lost.is_set():
                logger.warning("Network execution lease lost execution_id=%s", execution_id)
                return
            await self._store.persist_execution_output(execution_id, result)
            terminal = {
                "output": result.answer,
                "trace_id": str(result.trace_id) if result.trace_id else None,
                "streamed_output": result.streamed_output,
            }
            await self._store.mark_terminal_pending(
                execution_id,
                status="completed",
                result=terminal,
            )
            invocations = await self._store.invocations(execution_id)
            await self._finalizer.finalize(
                execution_id=execution_id,
                version=version,
                invocation_states=invocations,
                terminal_status="completed",
                output=result.answer,
                trace_id=result.trace_id,
                streamed_output=result.streamed_output,
            )
            await self._store.mark_persisted(execution_id, status="completed")
        except NetworkExecutionCancelled:
            await self._terminal_cancelled(execution_id, version)
        except NetworkBudgetExceeded as exc:
            await self._terminal_failure(
                execution_id,
                version,
                status="failed",
                code=exc.code,
                detail=str(exc),
                message=str(exc),
                uncertain=False,
            )
        except NetworkRuntimeFailure as exc:
            logger.exception("Network execution failed execution_id=%s", execution_id)
            await self._terminal_failure(
                execution_id,
                version,
                status="failed",
                code=exc.code,
                detail=exc.internal_detail,
                message=exc.safe_message,
                uncertain=False,
                trace_id=exc.trace_id,
                partial_result_available=exc.partial_result_available,
            )
        except Exception as exc:
            logger.exception("Network execution failed execution_id=%s", execution_id)
            await self._terminal_failure(
                execution_id,
                version,
                status="failed",
                code="runtime_error",
                detail=str(exc),
                message="The Network Run failed before producing a complete result.",
                uncertain=False,
            )
        finally:
            stop_heartbeat.set()
            await heartbeat_task

    async def _execute_with_cancellation(self, execution_id: UUID, execution_coro):
        """Interrupt the active Agent/provider task when Run cancellation is requested."""
        execution_task = asyncio.create_task(execution_coro)
        try:
            while True:
                done, _ = await asyncio.wait({execution_task}, timeout=0.2)
                if execution_task in done:
                    return await execution_task
                if await self._store.is_cancel_requested(execution_id):
                    execution_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await execution_task
                    await self._store.cancel_running_invocations(execution_id)
                    raise NetworkExecutionCancelled("Network execution was cancelled")
        finally:
            if not execution_task.done():
                execution_task.cancel()
                with suppress(asyncio.CancelledError):
                    await execution_task

    async def _heartbeat(
        self,
        execution_id: UUID,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._heartbeat_seconds)
                return
            except asyncio.TimeoutError:
                pass
            renewed = await self._store.renew_lease(
                execution_id,
                worker_id=self._worker_id,
                ttl_seconds=self._lease_ttl_seconds,
            )
            if not renewed:
                lease_lost.set()
                return

    async def _terminal_cancelled(self, execution_id: UUID, version) -> None:
        await self._store.cancel_running_invocations(execution_id)
        output = await self._store.partial_output(execution_id)
        invocations = await self._store.invocations(execution_id)
        root = next((item for item in invocations if int(item.get("depth") or 0) == 0), None)
        raw_trace_id = root.get("trace_id") if root is not None else None
        trace_id = UUID(str(raw_trace_id)) if raw_trace_id else None
        terminal = {
            "output": output,
            "trace_id": str(trace_id) if trace_id else None,
            "partial": bool(output),
            "cancelled": True,
        }
        await self._store.mark_terminal_pending(
            execution_id,
            status="cancelled",
            result=terminal,
        )
        await self._finalizer.finalize(
            execution_id=execution_id,
            version=version,
            invocation_states=invocations,
            terminal_status="cancelled",
            output=output,
            trace_id=trace_id,
        )
        await self._store.mark_persisted(execution_id, status="cancelled")

    async def _terminal_failure(
        self,
        execution_id: UUID,
        version,
        *,
        status: str,
        code: str,
        detail: str,
        message: str,
        uncertain: bool,
        trace_id: UUID | None = None,
        partial_result_available: bool = False,
    ) -> None:
        output = await self._store.partial_output(execution_id)
        invocations = await self._store.invocations(execution_id)
        completed_child_count = sum(
            1
            for item in invocations
            if str(item.get("status") or "") == "completed"
            and int(item.get("depth") or 0) > 0
            and bool(item.get("output_message") or item.get("parsed_output"))
        )
        root_partial_result_available = bool(output)
        terminal_has_partial = partial_result_available or root_partial_result_available
        payload = {
            "failure_code": code,
            "failure_detail": detail,
            "failure_message": message,
            "trace_id": str(trace_id) if trace_id else None,
            "uncertain": uncertain,
            "output": output,
            "partial": root_partial_result_available,
            "partial_result_available": terminal_has_partial,
            "root_partial_result_available": root_partial_result_available,
            "completed_child_results_available": completed_child_count > 0,
            "completed_child_result_count": completed_child_count,
        }
        await self._store.mark_terminal_pending(
            execution_id,
            status=status,
            result=payload,
        )
        await self._finalizer.finalize(
            execution_id=execution_id,
            version=version,
            invocation_states=invocations,
            terminal_status=status,
            output=output,
            trace_id=trace_id,
            failure_code=code,
            failure_detail=detail,
            failure_message=message,
            partial_result_available=terminal_has_partial,
            uncertain=uncertain,
        )
        await self._store.mark_persisted(
            execution_id,
            status="uncertain" if uncertain else status,
        )

    async def _finalize_failure(
        self,
        execution_id: UUID,
        version,
        *,
        code: str,
        detail: str,
        uncertain: bool,
    ) -> None:
        await self._finalizer.finalize(
            execution_id=execution_id,
            version=version,
            invocation_states=[],
            terminal_status="failed",
            output=None,
            trace_id=None,
            failure_code=code,
            failure_detail=detail,
            failure_message="The Network Run could not be prepared for execution.",
            uncertain=uncertain,
        )

    async def _resume_terminal(
        self,
        execution_id: UUID,
        version,
        state: dict[str, Any],
    ) -> None:
        terminal_status = str(state.get("terminal_status") or "uncertain")
        result = state.get("terminal_result")
        result = result if isinstance(result, dict) else {}
        trace_id = UUID(str(result["trace_id"])) if result.get("trace_id") else None
        invocations = await self._store.invocations(execution_id)
        await self._finalizer.finalize(
            execution_id=execution_id,
            version=version,
            invocation_states=invocations,
            terminal_status=terminal_status,
            output=result.get("output"),
            trace_id=trace_id,
            failure_code=result.get("failure_code"),
            failure_detail=result.get("failure_detail"),
            failure_message=result.get("failure_message"),
            partial_result_available=bool(result.get("partial_result_available")),
            uncertain=bool(result.get("uncertain")),
            streamed_output=bool(result.get("streamed_output")),
        )
        await self._store.mark_persisted(
            execution_id,
            status=(
                "uncertain"
                if result.get("uncertain")
                else terminal_status
            ),
        )


class NetworkExecutionConsumer(BaseInboxConsumer):
    def __init__(
        self,
        manager: RabbitMQManager,
        processor: NetworkExecutionProcessor,
        *,
        prefetch_count: int,
        worker_slots: int,
    ) -> None:
        self._manager = manager
        self._processor = processor
        self._prefetch_count = prefetch_count
        self._slots = asyncio.Semaphore(max(1, worker_slots))
        self._registered = asyncio.Event()

    async def consume(self) -> None:
        await self._manager.consume(
            queue_name="network.execution",
            routing_keys=[
                "network.execution.draft.requested.v1",
                "network.execution.staging.requested.v1",
                "network.execution.production.requested.v1",
            ],
            callback=self._handle,
            prefetch_count=self._prefetch_count,
        )
        self._registered.set()
        await asyncio.Event().wait()

    async def _handle(self, message: IncomingMessage) -> None:
        async with self._slots:
            try:
                payload = json.loads(message.body.decode())
                await self._processor.process(UUID(str(payload["execution_id"])))
                await message.ack()
            except Exception:
                logger.exception("Network execution message failed")
                await message.reject(requeue=False)

    async def persist_inbox(self, record: InboxRecord) -> None:
        return None

    async def acknowledge(self, message: IncomingMessage) -> None:
        await message.ack()

    async def reject(self, message: IncomingMessage, error: str) -> None:
        await message.reject(requeue=False)


class NetworkLeaseRecoveryWorker:
    """Recover terminal Redis state without replaying uncertain external work."""

    def __init__(
        self,
        *,
        loader: NetworkRuntimeLoader,
        store: RedisNetworkExecutionStore,
        finalizer: NetworkRuntimeFinalizer,
        lease_ttl_seconds: int,
    ) -> None:
        self._loader = loader
        self._store = store
        self._finalizer = finalizer
        self._lease_ttl_seconds = lease_ttl_seconds
        self._worker_id = f"network-recovery-{os.getpid()}"

    async def run(self) -> None:
        candidates = await self._loader.recovery_candidates(
            older_than_seconds=max(self._lease_ttl_seconds * 2, 30),
        )
        for execution_id in candidates:
            loaded = await self._loader.load(execution_id)
            if loaded is None:
                continue
            durable_status = str(loaded.execution.status)
            if durable_status in _TERMINAL_EXECUTION_STATUSES:
                continue

            state = await self._store.snapshot(execution_id)
            if not state:
                if durable_status == "queued":
                    continue

                await self._finalizer.finalize(
                    execution_id=execution_id,
                    version=loaded.version,
                    invocation_states=[],
                    terminal_status="failed",
                    output=None,
                    trace_id=None,
                    failure_code="execution_state_lost",
                    failure_detail=(
                        "Execution state disappeared after execution had started; "
                        "automatic replay was blocked."
                    ),
                    failure_message=(
                        "The Network execution state was lost after execution started."
                    ),
                    uncertain=True,
                )
                continue

            if state.get("status") == "terminal_pending_persist":
                result = state.get("terminal_result")
                result = result if isinstance(result, dict) else {}
                invocations = await self._store.invocations(execution_id)
                trace_id = (
                    UUID(str(result["trace_id"]))
                    if result.get("trace_id")
                    else None
                )
                await self._finalizer.finalize(
                    execution_id=execution_id,
                    version=loaded.version,
                    invocation_states=invocations,
                    terminal_status=str(
                        state.get("terminal_status") or "failed"
                    ),
                    output=result.get("output"),
                    trace_id=trace_id,
                    failure_code=result.get("failure_code"),
                    failure_detail=result.get("failure_detail"),
                    failure_message=result.get("failure_message"),
                    partial_result_available=bool(result.get("partial_result_available")),
                    uncertain=bool(result.get("uncertain")),
                    streamed_output=bool(result.get("streamed_output")),
                )
                await self._store.mark_persisted(
                    execution_id,
                    status=(
                        "uncertain"
                        if result.get("uncertain")
                        else str(state.get("terminal_status") or "failed")
                    ),
                )
                continue

            lease = await self._store.acquire_lease(
                execution_id,
                worker_id=self._worker_id,
                ttl_seconds=self._lease_ttl_seconds,
            )
            if lease is None:
                continue
            invocations = await self._store.invocations(execution_id)
            uncertain = bool(invocations)
            await self._finalizer.finalize(
                execution_id=execution_id,
                version=loaded.version,
                invocation_states=invocations,
                terminal_status="failed",
                output=None,
                trace_id=None,
                failure_code="worker_lease_expired",
                failure_detail=(
                    "Worker lease expired after execution started; automatic replay "
                    "was blocked to avoid duplicate external side effects."
                ),
                failure_message=(
                    "The Network worker lease expired before the Run could be finalized."
                ),
                uncertain=uncertain,
            )
            await self._store.mark_persisted(
                execution_id,
                status="uncertain" if uncertain else "failed",
            )
