from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Never

from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol

logger = logging.getLogger(__name__)


class WorkerRunner:
    def __init__(self, workers: list[WorkerProtocol]) -> None:
        self._workers = workers

    @classmethod
    def from_registries(cls, registries: list[WorkerRegistryProtocol]) -> WorkerRunner:
        workers: list[WorkerProtocol] = []
        for registry in registries:
            workers.extend(registry.iter_workers())
        return cls(workers=workers)

    async def run_once(self) -> None:
        for worker in self._workers:
            try:
                await worker.run()
            except Exception as exc:
                logger.exception("Worker %s failed: %s", type(worker).__name__, exc)

    async def run_loop(self, interval: float = 1.0) -> Never:
        stop = asyncio.Event()

        def _signal_handler() -> None:
            stop.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                pass

        try:
            while not stop.is_set():
                await self.run_once()
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
        finally:
            sys.exit(0)
