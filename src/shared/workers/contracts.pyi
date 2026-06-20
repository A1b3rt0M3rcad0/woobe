from typing import Protocol


class WorkerProtocol(Protocol):
    async def run(self) -> None: ...


class WorkerRegistryProtocol(Protocol):
    def register(self, worker: WorkerProtocol) -> None: ...
    def iter_workers(self) -> list[WorkerProtocol]: ...
