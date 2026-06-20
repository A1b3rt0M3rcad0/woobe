from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class WorkerProtocol(Protocol):
    async def run(self) -> None: ...


@runtime_checkable
class WorkerRegistryProtocol(Protocol):
    def iter_workers(self) -> list[WorkerProtocol]: ...
