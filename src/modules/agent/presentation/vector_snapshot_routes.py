from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from modules.agent.composition.composers.vector_snapshot_composers import (
    create_vector_snapshot as compose_create_vector_snapshot,
    get_collection_overview as compose_get_collection_overview,
    get_vector_snapshot as compose_get_vector_snapshot,
    list_vector_snapshots as compose_list_vector_snapshots,
    preview_vector_snapshot as compose_preview_vector_snapshot,
)
from modules.agent.application.dtos.vector_snapshot_dtos import (
    CreateVectorSnapshotInput,
    GetCollectionOverviewInput,
    GetVectorSnapshotInput,
    ListVectorSnapshotsInput,
    PreviewVectorSnapshotInput,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/agent/knowledge", tags=["knowledge", "agent"])


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "data": None},
    )


@router.get("/collections/{collection_id}/overview")
async def get_collection_overview(
    request: Request,
    collection_id: UUID,
    project_id: UUID,
):
    try:
        output = await compose_get_collection_overview(
            request.app.state.session_factory,
            GetCollectionOverviewInput(
                project_id=project_id,
                collection_id=collection_id,
            ),
        )
    except NotFoundError as exc:
        return _error(404, str(exc))
    return jsonable_encoder(
        {"success": True, "message": "ok", "data": output.model_dump()}
    )


@router.post("/collections/{collection_id}/vector-preview")
async def preview_vector_snapshot(request: Request, collection_id: UUID):
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        output = await compose_preview_vector_snapshot(
            request.app.state.session_factory,
            PreviewVectorSnapshotInput(
                collection_id=collection_id,
                **body,
            ),
        )
    except ConflictError as exc:
        return _error(409, str(exc))
    except NotFoundError as exc:
        return _error(404, str(exc))
    except ValidationError as exc:
        return _error(422, str(exc))
    return jsonable_encoder(
        {"success": True, "message": "ok", "data": output.model_dump()}
    )


@router.post("/collections/{collection_id}/vector-snapshots", status_code=202)
async def create_vector_snapshot(request: Request, collection_id: UUID):
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        output = await compose_create_vector_snapshot(
            request.app.state.session_factory,
            CreateVectorSnapshotInput(collection_id=collection_id, **body),
        )
    except ConflictError as exc:
        return _error(409, str(exc))
    except NotFoundError as exc:
        return _error(404, str(exc))
    except ValidationError as exc:
        return _error(422, str(exc))

    return jsonable_encoder(
        {"success": True, "message": "accepted", "data": output.model_dump()}
    )


@router.get("/collections/{collection_id}/vector-snapshots")
async def list_vector_snapshots(
    request: Request,
    collection_id: UUID,
    project_id: UUID,
):
    output = await compose_list_vector_snapshots(
        request.app.state.session_factory,
        ListVectorSnapshotsInput(
            project_id=project_id,
            collection_id=collection_id,
        ),
    )
    return jsonable_encoder(
        {
            "success": True,
            "message": "ok",
            "data": [item.model_dump() for item in output],
        }
    )


@router.get("/vector-snapshots/{snapshot_id}")
async def get_vector_snapshot(
    request: Request,
    snapshot_id: UUID,
    project_id: UUID | None = None,
):
    try:
        output = await compose_get_vector_snapshot(
            request.app.state.session_factory,
            GetVectorSnapshotInput(
                snapshot_id=snapshot_id,
                project_id=project_id,
            ),
        )
    except NotFoundError as exc:
        return _error(404, str(exc))
    return jsonable_encoder(
        {"success": True, "message": "ok", "data": output.model_dump()}
    )
