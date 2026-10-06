import re

from fastapi.responses import JSONResponse


class PackageBodyLimitExceeded(Exception):
    pass


class PackageBodyLimitsMiddleware:
    """Bound chunked bodies before multipart parsers or security helpers consume them."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").removeprefix(scope.get("root_path", ""))
        if (
            scope["type"] != "http"
            or scope.get("method") not in {"POST", "PUT", "PATCH"}
            or not re.match(r"^/projects/[^/]+/packages(?:/|$)", path)
        ):
            await self.app(scope, receive, send)
            return
        limit = (128 << 20) + (64 << 10) if path.endswith("/uploads") else 2 << 20
        size, exceeded, started = 0, False, False

        async def bounded_receive():
            nonlocal size, exceeded
            if exceeded:
                raise PackageBodyLimitExceeded()
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    exceeded = True
                    raise PackageBodyLimitExceeded()
            return message

        async def track_send(message):
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, bounded_receive, track_send)
        except PackageBodyLimitExceeded:
            if started:
                raise
            await JSONResponse(
                {
                    "success": False,
                    "message": "Package request exceeds its body limit",
                    "meta": {"complete": False},
                },
                status_code=413,
            )(scope, receive, send)
