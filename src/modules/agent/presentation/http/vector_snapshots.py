from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from modules.agent.application.dtos.vector_snapshot_dtos import (
    CreateVectorSnapshotInput,
    GetCollectionOverviewInput,
    GetVectorSnapshotInput,
    ListVectorSnapshotsInput,
    PreviewVectorSnapshotInput,
)
from modules.agent.composition.composers.vector_snapshot_composers import (
    create_vector_snapshot_composer,
    get_collection_overview_composer,
    get_vector_snapshot_composer,
    list_vector_snapshots_composer,
    preview_vector_snapshot_composer,
)
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "data": None},
    )


async def get_collection_overview(
    request: Request,
    collection_id: UUID,
    project_id: UUID,
):
    handler = get_collection_overview_composer()
    try:
        output = await handler(
            GetCollectionOverviewInput(
                project_id=project_id,
                collection_id=collection_id,
            )
        )
    except NotFoundError as exc:
        return _error(404, str(exc))
    return jsonable_encoder(
        {"success": True, "message": "ok", "data": output.model_dump()}
    )


async def preview_vector_snapshot(request: Request, collection_id: UUID):
    try:
        body = await request.json()
    except Exception:
        body = {}
    handler = preview_vector_snapshot_composer()
    try:
        output = await handler(
            PreviewVectorSnapshotInput(
                collection_id=collection_id,
                **body,
            )
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


async def create_vector_snapshot(request: Request, collection_id: UUID):
    try:
        body = await request.json()
    except Exception:
        body = {}
    handler = create_vector_snapshot_composer()
    try:
        output = await handler(
            CreateVectorSnapshotInput(collection_id=collection_id, **body)
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


async def list_vector_snapshots(
    request: Request,
    collection_id: UUID,
    project_id: UUID,
):
    handler = list_vector_snapshots_composer()
    output = await handler(
        ListVectorSnapshotsInput(
            project_id=project_id,
            collection_id=collection_id,
        )
    )
    return jsonable_encoder(
        {
            "success": True,
            "message": "ok",
            "data": [item.model_dump() for item in output],
        }
    )


async def get_vector_snapshot(
    request: Request,
    snapshot_id: UUID,
    project_id: UUID | None = None,
):
    handler = get_vector_snapshot_composer()
    try:
        output = await handler(
            GetVectorSnapshotInput(
                snapshot_id=snapshot_id,
                project_id=project_id,
            )
        )
    except NotFoundError as exc:
        return _error(404, str(exc))
    return jsonable_encoder(
        {"success": True, "message": "ok", "data": output.model_dump()}
    )
