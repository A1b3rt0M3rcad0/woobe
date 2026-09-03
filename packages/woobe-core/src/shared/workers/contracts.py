from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WorkerProtocol(Protocol):
    async def run(self) -> None: ...


@runtime_checkable
class WorkerRegistryProtocol(Protocol):
    def iter_workers(self) -> list[WorkerProtocol]: ...


@dataclass(frozen=True, slots=True)
class ModuleWorkerEntry:
    module_name: str
    registry_class: type[WorkerRegistryProtocol]
    register_func: Any
