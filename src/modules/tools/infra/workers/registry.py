from __future__ import annotations

from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class ToolsWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


assert isinstance(ToolsWorkerRegistry, type)
_check: WorkerRegistryProtocol = ToolsWorkerRegistry()
del _check
