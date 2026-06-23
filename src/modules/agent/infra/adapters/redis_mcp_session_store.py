from __future__ import annotations

import asyncio
import logging
import ssl
from urllib.parse import unquote, urlsplit

from modules.agent.application.ports import McpSessionStorePort

logger = logging.getLogger(__name__)


class _RedisProtocolError(RuntimeError):
    pass


class _AsyncRedisConnection:
    def __init__(self, url: str, timeout_seconds: float = 2.0) -> None:
        self._url = url
        self._timeout_seconds = timeout_seconds
        self._parsed = urlsplit(url)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def __aenter__(self) -> "_AsyncRedisConnection":
        host = self._parsed.hostname or "localhost"
        port = self._parsed.port or 6379
        use_tls = self._parsed.scheme == "rediss"
        ssl_context = ssl.create_default_context() if use_tls else None
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context),
            timeout=self._timeout_seconds,
        )
        await self._authenticate_if_needed()
        await self._select_db_if_needed()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

    async def _authenticate_if_needed(self) -> None:
        password = self._parsed.password
        if password is None:
            return
        username = self._parsed.username
        if username:
            await self.execute("AUTH", unquote(username), unquote(password))
        else:
            await self.execute("AUTH", unquote(password))

    async def _select_db_if_needed(self) -> None:
        path = (self._parsed.path or "").strip("/")
        if not path:
            return
        await self.execute("SELECT", path)

    async def execute(self, *parts: str | int) -> object:
        if self._reader is None or self._writer is None:
            raise _RedisProtocolError("Redis connection is not open")
        payload = self._encode_command(parts)
        self._writer.write(payload)
        await asyncio.wait_for(self._writer.drain(), timeout=self._timeout_seconds)
        return await asyncio.wait_for(self._read_response(), timeout=self._timeout_seconds)

    @staticmethod
    def _encode_command(parts: tuple[str | int, ...]) -> bytes:
        chunks = [f"*{len(parts)}\r\n".encode()]
        for part in parts:
            value = str(part).encode()
            chunks.append(f"${len(value)}\r\n".encode())
            chunks.append(value)
            chunks.append(b"\r\n")
        return b"".join(chunks)

    async def _read_line(self) -> bytes:
        if self._reader is None:
            raise _RedisProtocolError("Redis connection is not open")
        line = await self._reader.readline()
        if not line:
            raise _RedisProtocolError("Redis connection closed")
        if not line.endswith(b"\r\n"):
            raise _RedisProtocolError("Malformed Redis response")
        return line[:-2]

    async def _read_response(self) -> object:
        if self._reader is None:
            raise _RedisProtocolError("Redis connection is not open")
        prefix = await self._reader.readexactly(1)
        if prefix == b"+":
            return (await self._read_line()).decode()
        if prefix == b"-":
            raise _RedisProtocolError((await self._read_line()).decode())
        if prefix == b":":
            return int((await self._read_line()).decode())
        if prefix == b"$":
            length = int((await self._read_line()).decode())
            if length == -1:
                return None
            data = await self._reader.readexactly(length)
            await self._reader.readexactly(2)
            return data
        if prefix == b"*":
            count = int((await self._read_line()).decode())
            if count == -1:
                return None
            return [await self._read_response() for _ in range(count)]
        raise _RedisProtocolError(f"Unsupported Redis response prefix: {prefix!r}")


class RedisMcpSessionStore(McpSessionStorePort):
    def __init__(
        self,
        redis_url: str,
        *,
        key_prefix: str = "projectrai:mcp-session",
        timeout_seconds: float = 2.0,
    ) -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix.strip(":")
        self._timeout_seconds = timeout_seconds

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    async def get(self, key: str) -> str | None:
        try:
            async with _AsyncRedisConnection(self._redis_url, self._timeout_seconds) as redis:
                value = await redis.execute("GET", self._key(key))
            if isinstance(value, bytes):
                return value.decode()
            if isinstance(value, str):
                return value
            return None
        except Exception as exc:
            logger.warning("MCP Redis session get failed: %s", exc)
            return None

    async def set(self, key: str, session_id: str, ttl_seconds: int) -> None:
        try:
            async with _AsyncRedisConnection(self._redis_url, self._timeout_seconds) as redis:
                await redis.execute("SET", self._key(key), session_id, "EX", ttl_seconds)
        except Exception as exc:
            logger.warning("MCP Redis session set failed: %s", exc)

    async def delete(self, key: str) -> None:
        try:
            async with _AsyncRedisConnection(self._redis_url, self._timeout_seconds) as redis:
                await redis.execute("DEL", self._key(key))
        except Exception as exc:
            logger.warning("MCP Redis session delete failed: %s", exc)


def build_redis_mcp_session_store(redis_url: str | None) -> RedisMcpSessionStore | None:
    if not redis_url:
        return None
    parsed = urlsplit(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        logger.warning("Unsupported Redis URL scheme for MCP session store: %s", parsed.scheme)
        return None
    return RedisMcpSessionStore(redis_url)
