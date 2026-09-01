from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shared.observability.context import correlation_id_context, request_id_context
from shared.observability.metrics import runtime_metrics

logger = logging.getLogger(__name__)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _header_id(headers: Headers, name: str, *, fallback: str) -> str:
    value = headers.get(name, "").strip()
    return value if _SAFE_ID.fullmatch(value) else fallback


class RequestObservabilityMiddleware:
    def __init__(self, app: ASGIApp, *, max_request_bytes: int) -> None:
        self.app = app
        self.max_request_bytes = max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        generated_id = str(uuid4())
        request_id = _header_id(headers, "x-request-id", fallback=generated_id)
        correlation_id = _header_id(headers, "x-correlation-id", fallback=request_id)
        request_token = request_id_context.set(request_id)
        correlation_token = correlation_id_context.set(correlation_id)
        started_at = time.perf_counter()
        status_code = 500

        content_length = headers.get("content-length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = 0
            if declared_size > self.max_request_bytes:
                body = b'{"success":false,"message":"Request body too large","data":null}'
                response_headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"x-request-id", request_id.encode("ascii")),
                    (b"x-correlation-id", correlation_id.encode("ascii")),
                ]
                await send({"type": "http.response.start", "status": 413, "headers": response_headers})
                await send({"type": "http.response.body", "body": body})
                runtime_metrics.observe_http(
                    method=scope.get("method", "UNKNOWN"),
                    route=scope.get("path", "unknown"),
                    status_code=413,
                    duration_seconds=time.perf_counter() - started_at,
                )
                request_id_context.reset(request_token)
                correlation_id_context.reset(correlation_token)
                return

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
                response_headers["X-Correlation-ID"] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        finally:
            duration_seconds = time.perf_counter() - started_at
            route = scope.get("route")
            route_path = getattr(route, "path", scope.get("path", "unknown"))
            method = scope.get("method", "UNKNOWN")
            runtime_metrics.observe_http(
                method=method,
                route=route_path,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
            logger.info(
                "HTTP request completed",
                extra={
                    "http_method": method,
                    "http_route": route_path,
                    "http_status": status_code,
                    "duration_ms": round(duration_seconds * 1000, 3),
                },
            )
            request_id_context.reset(request_token)
            correlation_id_context.reset(correlation_token)
