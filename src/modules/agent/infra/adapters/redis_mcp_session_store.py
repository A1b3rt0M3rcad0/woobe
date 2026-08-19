from __future__ import annotations

import logging
from urllib.parse import urlsplit

from modules.agent.application.interfaces.ports import McpSessionStorePort
from shared.infra.cache.kv_store import RedisKeyValueStore

logger = logging.getLogger(__name__)


class RedisMcpSessionStore(McpSessionStorePort):
    def __init__(
        self,
        redis_url: str,
        *,
        key_prefix: str = "projectrai:mcp-session",
        timeout_seconds: float = 2.0,
    ) -> None:
        self._store = RedisKeyValueStore(
            redis_url,
            key_prefix=key_prefix,
            timeout_seconds=timeout_seconds,
        )

    async def get(self, key: str) -> str | None:
        try:
            return await self._store.get(key)
        except Exception as exc:
            logger.warning("MCP session cache get failed: %s", exc)
            return None

    async def set(self, key: str, session_id: str, ttl_seconds: int) -> None:
        try:
            await self._store.set(key, session_id, ttl_seconds)
        except Exception as exc:
            logger.warning("MCP session cache set failed: %s", exc)

    async def delete(self, key: str) -> None:
        try:
            await self._store.delete(key)
        except Exception as exc:
            logger.warning("MCP session cache delete failed: %s", exc)


def build_redis_mcp_session_store(
    redis_url: str | None,
    *,
    enabled: bool = True,
    key_prefix: str = "projectrai:mcp-session",
    timeout_seconds: float = 2.0,
) -> RedisMcpSessionStore | None:
    if not enabled or not redis_url:
        return None
    parsed = urlsplit(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        logger.warning("Unsupported cache URL scheme for MCP sessions: %s", parsed.scheme)
        return None
    return RedisMcpSessionStore(
        redis_url,
        key_prefix=key_prefix,
        timeout_seconds=timeout_seconds,
    )
