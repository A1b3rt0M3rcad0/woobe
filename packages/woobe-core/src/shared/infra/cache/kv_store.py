from __future__ import annotations

import asyncio
import ssl
from urllib.parse import unquote, urlsplit

from shared.infra.cache.key_value_store import AsyncKeyValueStore


class KeyValueStoreError(RuntimeError):
    pass


class RedisKeyValueStore(AsyncKeyValueStore):
    def __init__(self, url: str, *, key_prefix: str = "projectrai", timeout_seconds: float = 2.0) -> None:
        self.url = url
        self.key_prefix = key_prefix.strip(":")
        self.timeout_seconds = timeout_seconds
        self._parsed = urlsplit(url)

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    async def get(self, key: str) -> str | None:
        value = await self._execute("GET", self._key(key))
        if isinstance(value, bytes):
            return value.decode()
        if isinstance(value, str):
            return value
        return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._execute("SET", self._key(key), value, "EX", int(ttl_seconds))

    async def delete(self, key: str) -> None:
        await self._execute("DEL", self._key(key))

    async def _authenticate(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        password = self._parsed.password
        if password is None:
            return
        decoded_password = unquote(password)
        username = self._parsed.username
        if username is not None:
            await self._send(reader, writer, "AUTH", unquote(username), decoded_password)
        else:
            await self._send(reader, writer, "AUTH", decoded_password)

    async def _execute(self, *parts: str | int) -> object:
        host = self._parsed.hostname or "localhost"
        port = self._parsed.port or 6379
        use_tls = self._parsed.scheme.endswith("s")
        ssl_context = ssl.create_default_context() if use_tls else None
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context),
            timeout=self.timeout_seconds,
        )
        try:
            await self._authenticate(reader, writer)
            path = (self._parsed.path or "").strip("/")
            if path:
                await self._send(reader, writer, "SELECT", path)
            return await self._send(reader, writer, *parts)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _send(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *parts: str | int,
    ) -> object:
        writer.write(self._encode(parts))
        await asyncio.wait_for(writer.drain(), timeout=self.timeout_seconds)
        return await asyncio.wait_for(self._read_response(reader), timeout=self.timeout_seconds)

    @staticmethod
    def _encode(parts: tuple[str | int, ...]) -> bytes:
        chunks = [f"*{len(parts)}\r\n".encode()]
        for part in parts:
            value = str(part).encode()
            chunks.append(f"${len(value)}\r\n".encode())
            chunks.append(value)
            chunks.append(b"\r\n")
        return b"".join(chunks)

    async def _line(self, reader: asyncio.StreamReader) -> bytes:
        line = await reader.readline()
        if not line:
            raise KeyValueStoreError("Connection closed")
        if not line.endswith(b"\r\n"):
            raise KeyValueStoreError("Malformed response")
        return line[:-2]

    async def _read_response(self, reader: asyncio.StreamReader) -> object:
        prefix = await reader.readexactly(1)
        if prefix == b"+":
            return (await self._line(reader)).decode()
        if prefix == b"-":
            raise KeyValueStoreError((await self._line(reader)).decode())
        if prefix == b":":
            return int((await self._line(reader)).decode())
        if prefix == b"$":
            length = int((await self._line(reader)).decode())
            if length == -1:
                return None
            data = await reader.readexactly(length)
            await reader.readexactly(2)
            return data
        if prefix == b"*":
            count = int((await self._line(reader)).decode())
            if count == -1:
                return None
            return [await self._read_response(reader) for _ in range(count)]
        raise KeyValueStoreError("Unsupported response")
