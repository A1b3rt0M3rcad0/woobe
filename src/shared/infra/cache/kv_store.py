from __future__ import annotations

from shared.infra.cache.key_value_store import AsyncKeyValueStore


class NetworkKeyValueStore(AsyncKeyValueStore):
    def __init__(self, url: str, *, key_prefix: str = "projectrai", timeout_seconds: float = 2.0) -> None:
        self.url = url
        self.key_prefix = key_prefix.strip(":")
        self.timeout_seconds = timeout_seconds

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None
