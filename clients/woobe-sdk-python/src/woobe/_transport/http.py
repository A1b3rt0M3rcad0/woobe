from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from woobe._transport.sse import SseDecoder, SseFrame
from woobe.errors import (
    WoobeAuthenticationError,
    WoobeConnectionError,
    WoobeProtocolError,
    WoobeRequestError,
)


class RuntimeTransport:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, read=None)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def stream_new_run(
        self,
        *,
        key: str,
        message: str,
        session_id: str | None,
        external_context: dict[str, Any] | None,
        idempotency_key: str,
    ) -> AsyncIterator[SseFrame]:
        payload: dict[str, Any] = {"message": message}
        if session_id is not None:
            payload["session_id"] = session_id
        if external_context is not None:
            payload["external_context"] = external_context
        async for frame in self._stream(
            method="POST",
            path="/v1/run/stream",
            key=key,
            json_body=payload,
            extra_headers={"Idempotency-Key": idempotency_key},
        ):
            yield frame

    async def validate_contracts(
        self,
        *,
        key: str,
        output_contract: dict[str, Any] | None,
        external_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            response = await self._http().post(
                "/v1/contracts/validate",
                headers=self._json_headers(key),
                json={
                    "output_contract": output_contract,
                    "external_context": external_context,
                },
            )
        except httpx.RequestError as exc:
            raise WoobeConnectionError(
                "Could not validate Woobe Runtime contracts"
            ) from exc

        await self._raise_for_status(response)
        try:
            body = response.json()
        except ValueError as exc:
            raise WoobeProtocolError(
                "Runtime contract validation response contains invalid JSON"
            ) from exc

        if not isinstance(body, dict):
            raise WoobeProtocolError(
                "Runtime contract validation response has an invalid envelope"
            )
        data = body.get("data")
        if body.get("success") is not True or not isinstance(data, dict):
            raise WoobeProtocolError(
                "Runtime contract validation response has an invalid envelope"
            )
        return data

    async def stream_run(self, *, key: str, run_id: str) -> AsyncIterator[SseFrame]:
        async for frame in self._stream(
            method="GET",
            path=f"/v1/runs/{run_id}/stream",
            key=key,
        ):
            yield frame

    async def resolve_active_run(self, *, key: str, session_id: str) -> str | None:
        try:
            response = await self._http().get(
                f"/v1/sessions/{session_id}/active-run",
                headers=self._headers(key),
            )
        except httpx.RequestError as exc:
            raise WoobeConnectionError("Could not resolve the active Woobe Run") from exc

        await self._raise_for_status(response)
        try:
            body = response.json()
        except ValueError as exc:
            raise WoobeProtocolError("Active Run response contains invalid JSON") from exc

        data = body.get("data") if isinstance(body, dict) else None
        if data is None:
            return None
        if not isinstance(data, dict):
            raise WoobeProtocolError("Active Run response has an invalid data envelope")
        run_id = data.get("run_id")
        if run_id is None:
            return None
        if not isinstance(run_id, str) or not run_id.strip():
            raise WoobeProtocolError("Active Run response has an invalid run_id")
        return run_id

    async def _stream(
        self,
        *,
        method: str,
        path: str,
        key: str,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncIterator[SseFrame]:
        headers = self._headers(key)
        if extra_headers:
            headers.update(extra_headers)

        try:
            async with self._http().stream(
                method,
                path,
                headers=headers,
                json=json_body,
            ) as response:
                await self._raise_for_status(response)
                decoder = SseDecoder()
                async for line in response.aiter_lines():
                    frame = decoder.feed_line(line)
                    if frame is not None:
                        yield frame
                final_frame = decoder.finish()
                if final_frame is not None:
                    yield final_frame
        except WoobeRequestError:
            raise
        except httpx.RequestError as exc:
            raise WoobeConnectionError("Woobe Runtime stream connection failed") from exc

    @staticmethod
    def _json_headers(key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _headers(key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {key}",
            "Accept": "text/event-stream",
            "Accept-Encoding": "identity",
            "Content-Type": "application/json",
        }

    @staticmethod
    async def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        raw = await response.aread()
        detail = raw.decode("utf-8", errors="replace").strip()
        message = f"Woobe Runtime request failed ({response.status_code})"
        if detail:
            message = f"{message}: {detail[:500]}"
        if response.status_code in {401, 403}:
            raise WoobeAuthenticationError(message, status_code=response.status_code)
        raise WoobeRequestError(message, status_code=response.status_code)
