from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self


class UnitOfWork(ABC):
    """Framework-neutral transactional lifecycle contract."""

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...
