from modules.package.background_boundary import build_package_executor
from woobe_workers.contracts import WorkerProtocol


class PackageOperationWorker:
    def __init__(self, executor):
        self._executor = executor

    async def run(self):
        for _ in range(4):
            if not await self._executor.run_once():
                return


class PackageWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None):
        self._workers = workers or []

    def register(self, worker: WorkerProtocol):
        self._workers.append(worker)

    def iter_workers(self):
        return list(self._workers)


def register_package_workers(registry, settings, engine, rabbitmq_manager=None):
    registry.register(PackageOperationWorker(build_package_executor()))
