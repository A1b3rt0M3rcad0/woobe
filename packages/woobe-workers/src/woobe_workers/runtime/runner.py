from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from shared.observability.metrics import runtime_metrics
from woobe_workers.contracts import WorkerProtocol, WorkerRegistryProtocol
from woobe_workers.runtime.inbox_consumer_base import BaseInboxConsumer

logger = logging.getLogger(__name__)

_POLL_INTERVAL: float = 1.0


@dataclass
class WorkerHealth:
    worker_name: str
    worker_type: str
    is_running: bool
    started_at: datetime | None = None
    last_run_at: datetime | None = None
    error: str | None = None


class WorkerRunner:
    def __init__(self, workers: list[WorkerProtocol]) -> None:
        self._workers = workers
        self._tasks: list[asyncio.Task[None]] = []
        self._health: dict[str, WorkerHealth] = {}
        self._stop_event = asyncio.Event()

    @classmethod
    def from_registries(
        cls,
        registries: list[WorkerRegistryProtocol],
        *,
        extra_workers: Sequence[WorkerProtocol] = (),
    ) -> WorkerRunner:
        workers: list[WorkerProtocol] = []
        for registry in registries:
            workers.extend(registry.iter_workers())
        workers.extend(extra_workers)
        return cls(workers=workers)

    def _health_key(self, worker: WorkerProtocol) -> str:
        return type(worker).__name__

    def _classify(self, worker: WorkerProtocol) -> str:
        if isinstance(worker, BaseInboxConsumer) or bool(
            getattr(worker, "long_lived", False)
        ):
            return "long-lived"
        return "poller"

    def _record_failure(self, key: str, error: Exception) -> None:
        health = self._health[key]
        health.error = type(error).__name__
        runtime_metrics.increment_worker_failure(
            worker=key,
            worker_type=health.worker_type,
        )

    async def start(self) -> None:
        started_at = datetime.now(timezone.utc)
        for worker in self._workers:
            key = self._health_key(worker)
            worker_type = self._classify(worker)
            self._health[key] = WorkerHealth(
                worker_name=key,
                worker_type=worker_type,
                is_running=True,
                started_at=started_at,
            )
            if worker_type == "long-lived":
                task = asyncio.create_task(self._run_long_lived(worker, key), name=key)
            else:
                task = asyncio.create_task(self._run_poller(worker, key), name=key)
            self._tasks.append(task)
            logger.info(
                "Worker started",
                extra={"worker_name": key, "worker_type": worker_type},
            )

    async def _run_long_lived(self, worker: WorkerProtocol, key: str) -> None:
        try:
            await worker.run()
        except asyncio.CancelledError:
            logger.info("Worker cancelled", extra={"worker_name": key})
            raise
        except Exception as exc:
            logger.exception("Worker failed", extra={"worker_name": key})
            self._record_failure(key, exc)
        finally:
            self._health[key].is_running = False

    async def _run_poller(self, worker: WorkerProtocol, key: str) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    await worker.run()
                    health = self._health[key]
                    health.last_run_at = datetime.now(timezone.utc)
                    health.error = None
                except Exception as exc:
                    logger.exception("Worker poll failed", extra={"worker_name": key})
                    self._record_failure(key, exc)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=_POLL_INTERVAL)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("Worker cancelled", extra={"worker_name": key})
            raise
        finally:
            self._health[key].is_running = False

    async def stop(self) -> None:
        self._stop_event.set()
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        for health in self._health.values():
            health.is_running = False

    def get_health(self) -> list[WorkerHealth]:
        return list(self._health.values())

    async def run_once(self) -> None:
        for worker in self._workers:
            try:
                await worker.run()
            except Exception:
                key = self._health_key(worker)
                worker_type = self._classify(worker)
                runtime_metrics.increment_worker_failure(
                    worker=key,
                    worker_type=worker_type,
                )
                logger.exception("Worker failed", extra={"worker_name": key})
