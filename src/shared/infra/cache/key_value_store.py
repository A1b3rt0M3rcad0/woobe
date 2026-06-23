from __future__ import annotations

from abc import ABC, abstractmethod


class AsyncKeyValueStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> str | None:
        ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...
