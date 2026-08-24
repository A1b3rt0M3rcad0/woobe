from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from aio_pika import IncomingMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.network.application.runtime import (
    NetworkBudgetExceeded,
    NetworkExecutionCancelled,
    NetworkExecutor,
)
from modules.network.application.runtime_failures import NetworkRuntimeFailure
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkVersionModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository
from modules.network.infra.runtime import (
    ProjectRAIAgentInvoker,
    SQLNetworkExecutionStore,
)
from shared.infra.config import Settings
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.inbox_consumer_base import BaseInboxConsumer, InboxRecord

logger = logging.getLogger(__name__)


class NetworkExecutionProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        settings: Settings,
        http_executor: HttpToolExecutor,
        lease_ttl_seconds: int,
        heartbeat_seconds: int,
        worker_id: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._lease_ttl_seconds = lease_ttl_seconds
        self._heartbeat_seconds = heartbeat_seconds
        self._worker_id = worker_id or f"network-worker-{os.getpid()}"
        self._agent_invoker = ProjectRAIAgentInvoker(
            self._settings,
            http_executor,
        )

    async def process(self, execution_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            repository = NetworkRuntimeRepository(session)
            execution = await repository.claim_execution(
                execution_id,
                worker_id=self._worker_id,
                lease_ttl_seconds=self._lease_ttl_seconds,
            )
            if execution is None:
                return
            await repository.append_event(execution, "execution_started", {})
            generation = execution.lease_generation

        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None:
                return
            version = (
                await session.get(NetworkVersionModel, execution.network_version_id)
                if execution.network_version_id
                else None
            )
            if version is None and not (
                execution.draft_revision is not None
                and execution.definition_snapshot
                and execution.resolved_bindings_snapshot
            ):
                await self._fail(
                    execution_id,
                    generation,
                    "version_missing",
                    "Pinned Network version not found",
                )
                return

        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat(execution_id, generation, stop_heartbeat, lease_lost)
        )
        try:
            executor = NetworkExecutor(
                invoker=self._agent_invoker,
                store=SQLNetworkExecutionStore(self._session_factory),
            )
            result = await executor.execute(execution, version)
            if lease_lost.is_set():
                logger.warning(
                    "Network execution lease lost execution_id=%s", execution_id
                )
                return
            await self._complete(
                execution_id,
                generation,
                output=result.answer,
                trace_id=result.trace_id,
                streamed_output=result.streamed_output,
            )
        except NetworkExecutionCancelled:
            await self._terminal(
                execution_id, generation, "cancelled", "execution_cancelled", {}
            )
        except NetworkBudgetExceeded as exc:
            await self._fail(
                execution_id,
                generation,
                "budget_exceeded",
                str(exc),
                stage="network_budget",
                safe_message=str(exc),
            )
        except NetworkRuntimeFailure as exc:
            logger.exception("Network execution failed execution_id=%s", execution_id)
            await self._fail(
                execution_id,
                generation,
                exc.code,
                exc.internal_detail,
                stage=exc.stage,
                safe_message=exc.safe_message,
                retryable=exc.retryable,
                cause_invocation_id=exc.invocation_id,
                cause_node_id=exc.node_id,
                cause_agent_id=exc.agent_id,
                trace_id=exc.trace_id,
            )
        except Exception as exc:
            logger.exception("Network execution failed execution_id=%s", execution_id)
            await self._fail(
                execution_id,
                generation,
                "runtime_error",
                str(exc),
                stage="network_runtime",
                safe_message="Network execution failed.",
            )
        finally:
            stop_heartbeat.set()
            await heartbeat_task

    async def _heartbeat(
        self,
        execution_id: UUID,
        generation: int,
        stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._heartbeat_seconds)
                return
            except asyncio.TimeoutError:
                pass
            async with self._session_factory() as session, session.begin():
                renewed = await NetworkRuntimeRepository(session).renew_lease(
                    execution_id,
                    worker_id=self._worker_id,
                    generation=generation,
                    lease_ttl_seconds=self._lease_ttl_seconds,
                )
                if not renewed:
                    lease_lost.set()
                    return

    async def _complete(
        self,
        execution_id: UUID,
        generation: int,
        *,
        output: str,
        trace_id: UUID | None,
        streamed_output: bool,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            execution = await session.scalar(
                select(NetworkExecutionModel)
                .where(
                    NetworkExecutionModel.id == execution_id,
                    NetworkExecutionModel.status == "running",
                    NetworkExecutionModel.lease_owner == self._worker_id,
                    NetworkExecutionModel.lease_generation == generation,
                )
                .with_for_update()
            )
            if execution is None:
                return
            repository = NetworkRuntimeRepository(session)
            await repository.mark_completed(
                execution, output=output, root_trace_id=trace_id
            )
            if output and not streamed_output:
                await repository.append_event(
                    execution,
                    "token",
                    {"content": output, "channel": "final", "visibility": "assistant"},
                )
            await repository.append_event(
                execution,
                "execution_completed",
                {"trace_id": str(trace_id) if trace_id else None},
            )

    async def _fail(
        self,
        execution_id: UUID,
        generation: int,
        code: str,
        detail: str,
        *,
        stage: str = "network_runtime",
        safe_message: str = "Network execution failed.",
        retryable: bool = False,
        cause_invocation_id: UUID | None = None,
        cause_node_id: UUID | None = None,
        cause_agent_id: UUID | None = None,
        trace_id: UUID | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            execution = await session.scalar(
                select(NetworkExecutionModel)
                .where(
                    NetworkExecutionModel.id == execution_id,
                    NetworkExecutionModel.lease_owner == self._worker_id,
                    NetworkExecutionModel.lease_generation == generation,
                )
                .with_for_update()
            )
            if execution is None:
                return
            repository = NetworkRuntimeRepository(session)
            await repository.mark_failed(
                execution,
                code=code,
                detail=detail,
                root_trace_id=trace_id,
            )
            await repository.append_event(
                execution,
                "execution_failed",
                {
                    "code": code,
                    "stage": stage,
                    "message": safe_message,
                    "retryable": retryable,
                    "cause_invocation_id": str(cause_invocation_id)
                    if cause_invocation_id
                    else None,
                    "cause_node_id": str(cause_node_id) if cause_node_id else None,
                    "cause_agent_id": str(cause_agent_id) if cause_agent_id else None,
                    "trace_id": str(trace_id) if trace_id else None,
                },
            )

    async def _terminal(
        self,
        execution_id: UUID,
        generation: int,
        status: str,
        event_type: str,
        payload: dict,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            execution = await session.scalar(
                select(NetworkExecutionModel)
                .where(
                    NetworkExecutionModel.id == execution_id,
                    NetworkExecutionModel.lease_owner == self._worker_id,
                    NetworkExecutionModel.lease_generation == generation,
                )
                .with_for_update()
            )
            if execution is None:
                return
            execution.status = status
            execution.completed_at = datetime.now(timezone.utc)
            execution.lease_owner = None
            execution.lease_expires_at = None
            await NetworkRuntimeRepository(session).append_event(
                execution,
                event_type,
                payload,
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
                execution_id = UUID(str(payload["execution_id"]))
                await self._processor.process(execution_id)
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


class NetworkOutboxDispatcherWorker:
    def __init__(self, engine: AsyncEngine, manager: RabbitMQManager) -> None:
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        self._manager = manager
        self._worker_id = f"network-outbox-{os.getpid()}"

    async def run(self) -> None:
        from modules.network.infra.database.repositories import NetworkOutboxRepository

        async with self._session_factory() as session, session.begin():
            repository = NetworkOutboxRepository(session)
            events = await repository.claim_batch(limit=50, worker_id=self._worker_id)
            for event in events:
                try:
                    await self._manager.publish(
                        routing_key=event.routing_key,
                        payload=json.dumps(event.payload),
                        correlation_id=str(event.correlation_id or ""),
                        message_id=str(event.id),
                    )
                    await repository.mark_published(event)
                except Exception as exc:
                    await repository.mark_retryable(event, str(exc))


class NetworkLeaseRecoveryWorker:
    """Fails stale executions safely instead of repeating unknown side effects."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def run(self) -> None:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(NetworkExecutionModel)
                .where(
                    NetworkExecutionModel.status == "running",
                    NetworkExecutionModel.lease_expires_at < now,
                )
                .with_for_update(skip_locked=True)
                .limit(50)
            )
            for execution in result.scalars():
                has_invocations = bool(
                    await session.scalar(
                        select(NetworkInvocationModel.id)
                        .where(
                            NetworkInvocationModel.network_execution_id == execution.id
                        )
                        .limit(1)
                    )
                )
                execution.status = "uncertain" if has_invocations else "failed"
                execution.failure_code = "worker_lease_expired"
                execution.failure_detail = (
                    "Worker lease expired after execution started; automatic replay was blocked "
                    "to avoid duplicating external side effects."
                )
                execution.completed_at = now
                execution.lease_owner = None
                execution.lease_expires_at = None
                await NetworkRuntimeRepository(session).append_event(
                    execution,
                    "execution_failed",
                    {
                        "code": "worker_lease_expired",
                        "stage": "worker_lease",
                        "message": (
                            "The Network worker stopped before completion. "
                            "Automatic replay was blocked to avoid duplicate side "
                            "effects."
                        ),
                        "retryable": False,
                        "uncertain": has_invocations,
                    },
                )
