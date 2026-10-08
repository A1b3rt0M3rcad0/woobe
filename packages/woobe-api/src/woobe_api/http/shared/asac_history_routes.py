"""Read-only transports; owner entrypoints supply tenancy and history readers."""
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from shared.contracts.errors import AuthorizationError


def history_router(prefix, builder, kind):
    router = APIRouter(prefix=prefix, tags=[kind.lower(), "asac-history"])

    def actor(request):
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise AuthorizationError("Administrative authentication is required")
        return principal

    def response(data):
        return JSONResponse(jsonable_encoder({"success": True, "message": "ok", "data": data,
                                             "meta": {"complete": data["complete"]}}))

    @router.get("/history")
    async def history(project_id: UUID, resource_id: UUID, request: Request,
                      stream: str = "releases", cursor: str | None = None,
                      limit: int = Query(default=100, ge=1, le=200)):
        return response(await builder().fetch(project_id=project_id, resource_id=resource_id,
                                             principal=actor(request), stream=stream, cursor=cursor, limit=limit))

    @router.get("/current")
    async def current(project_id: UUID, resource_id: UUID, request: Request, environment: str = "production"):
        return response(await builder().current(project_id=project_id, resource_id=resource_id,
                                               principal=actor(request), environment=environment))

    return router
