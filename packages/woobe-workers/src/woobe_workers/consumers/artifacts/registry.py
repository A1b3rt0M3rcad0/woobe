import asyncio
import socket
from uuid import uuid4

from modules.artifacts.background_boundary import build_processing_runner


class ArtifactProcessingWorker:
    def __init__(self, engine, settings):
        self._runners = [(f'artifact-documents:{socket.gethostname()}:{uuid4().hex}'[:128],
                          build_processing_runner(engine, settings))
                         for _ in range(settings.artifact_processing_worker_slots)]

    async def run(self):
        tasks = [asyncio.create_task(runner.run_once(worker_id)) for worker_id, runner in self._runners]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    raise result
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


class ArtifactsWorkerRegistry:
    def __init__(self):
        self._workers = []

    def register(self, worker):
        self._workers.append(worker)

    def iter_workers(self):
        return list(self._workers)


def register_artifacts_workers(registry, settings, engine, rabbitmq_manager=None):
    # Like existing Ask/Vector Snapshot pollers, this durable queue keeps working
    # with the broker absent. It runs within the existing WorkerRunner lifecycle.
    registry.register(ArtifactProcessingWorker(engine, settings))
