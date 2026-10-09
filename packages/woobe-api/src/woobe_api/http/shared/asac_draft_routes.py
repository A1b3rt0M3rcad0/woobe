"""Strict versioned Draft transports; validation and writes belong to Core owners."""
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from shared.contracts.asac_requests import OpenASaCDraft, SaveASaCDraft, RegisterASaCRevision
from shared.contracts.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from modules.package.entrypoint import PackageError, build_snapshot_artifacts


def draft_router(prefix, builder, kind):
    router = APIRouter(prefix=prefix, tags=[kind.lower(), "asac-drafts"])

    def store():
        return builder(artifacts=build_snapshot_artifacts())

    def actor(request):
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise AuthorizationError("Administrative authentication is required")
        return principal

    async def invoke(awaitable):
        try:
            return await awaitable
        except (PackageError, ConflictError, NotFoundError, ValidationError) as exc:
            if isinstance(exc, PackageError):
                code, message = exc.code, str(exc)
                status = 422
            else:
                code, separator, message = str(exc).partition(":")
                if not code.startswith("ASAC_"):
                    raise
                status = 409 if isinstance(exc, ConflictError) else 404 if isinstance(exc, NotFoundError) else 422
                message = message.strip() or code
            return JSONResponse({"success": False, "message": message,
                "data": {"asac_schema_version": "1.0", "diagnostics": [{"code": code, "message": message}]},
                "meta": {"complete": False}}, status_code=status)

    def response(data):
        if isinstance(data, JSONResponse):
            return data
        return JSONResponse(jsonable_encoder({"success": True, "message": "ok", "data": data,
            "meta": {"complete": data.get("complete", True)}}))

    @router.get("/drafts")
    async def drafts(project_id: UUID, resource_id: UUID, request: Request):
        return response(await invoke(store().list_drafts(project_id=project_id, resource_id=resource_id, principal=actor(request))))

    @router.post("/drafts")
    async def open_draft(project_id: UUID, resource_id: UUID, body: OpenASaCDraft, request: Request):
        return response(await invoke(store().open_draft(project_id=project_id, resource_id=resource_id, principal=actor(request), request=body)))

    @router.get("/drafts/{draft_id}")
    async def draft(project_id: UUID, resource_id: UUID, draft_id: UUID, request: Request):
        return response(await invoke(store().get_draft(project_id=project_id, resource_id=resource_id, draft_id=draft_id, principal=actor(request))))

    @router.put("/drafts/{draft_id}")
    async def save_draft(project_id: UUID, resource_id: UUID, draft_id: UUID, body: SaveASaCDraft, request: Request):
        return response(await invoke(store().save_draft(project_id=project_id, resource_id=resource_id, draft_id=draft_id, principal=actor(request), request=body)))

    @router.post("/revisions")
    async def register_revision(project_id: UUID, resource_id: UUID, body: RegisterASaCRevision, request: Request):
        return response(await invoke(store().register_revision(project_id=project_id, resource_id=resource_id, principal=actor(request), request=body)))

    @router.get("/revisions")
    async def revisions(project_id: UUID, resource_id: UUID, request: Request,
                        cursor: str | None = None, limit: int = Query(default=100, ge=1, le=200)):
        return response(await invoke(store().list_revisions(project_id=project_id,
            resource_id=resource_id, principal=actor(request), cursor=cursor, limit=limit)))

    @router.get("/revisions/{revision_id}")
    async def revision(project_id: UUID, resource_id: UUID, revision_id: str, request: Request):
        return response(await invoke(store().get_revision(project_id=project_id, resource_id=resource_id, revision_id=revision_id, principal=actor(request))))

    @router.get("/revisions/{revision_id}/artifact/receipt")
    async def revision_artifact_receipt(project_id: UUID, resource_id: UUID, revision_id: str, request: Request):
        result = await invoke(store().revision_transfer(project_id=project_id,
            resource_id=resource_id, revision_id=revision_id, principal=actor(request)))
        if isinstance(result, JSONResponse):
            return result
        receipt, _ = result
        return response(receipt)

    @router.get("/revisions/{revision_id}/artifact")
    async def revision_artifact(project_id: UUID, resource_id: UUID, revision_id: str, request: Request):
        result = await invoke(store().revision_transfer(project_id=project_id,
            resource_id=resource_id, revision_id=revision_id, principal=actor(request)))
        if isinstance(result, JSONResponse):
            return result
        receipt, content = result
        return Response(content=content, media_type="application/gzip", headers={
            "Content-Length": str(receipt["size_bytes"]),
            "X-Woobe-Transport-Sha256": receipt["transport_digest"],
            "X-Woobe-Artifact-Digest": receipt["artifact_digest"].removeprefix("sha256:"),
            "X-Woobe-Record-Digest": receipt["record_digest"],
            "Cache-Control": "no-store"})

    @router.get("/revisions/{revision_id}/author/receipt")
    async def revision_author_receipt(project_id: UUID, resource_id: UUID, revision_id: str, request: Request):
        result = await invoke(store().author_transfer(project_id=project_id,
            resource_id=resource_id, revision_id=revision_id, principal=actor(request)))
        if isinstance(result, JSONResponse):
            return result
        receipt, _ = result
        return response(receipt)

    @router.get("/revisions/{revision_id}/author")
    async def revision_author(project_id: UUID, resource_id: UUID, revision_id: str, request: Request):
        result = await invoke(store().author_transfer(project_id=project_id,
            resource_id=resource_id, revision_id=revision_id, principal=actor(request)))
        if isinstance(result, JSONResponse):
            return result
        receipt, content = result
        return Response(content=content, media_type="application/gzip", headers={
            "Content-Length": str(receipt["size_bytes"]), "Cache-Control": "no-store",
            "X-Woobe-Transport-Sha256": receipt["transport_digest"],
            "X-Woobe-Author-Digest": receipt["author_digest"],
            "X-Woobe-Record-Digest": receipt["record_digest"]})

    @router.get("/operations/{operation_id}")
    async def operation(project_id: UUID, resource_id: UUID, operation_id: UUID, request: Request):
        return response(await invoke(store().operation(project_id=project_id, resource_id=resource_id, operation_id=operation_id, principal=actor(request))))

    return router
