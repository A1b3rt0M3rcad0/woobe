from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from woobe_api.http.agent import vector_snapshots as handlers

router = APIRouter(prefix="/agent/knowledge", tags=["knowledge", "agent"])


@router.get("/collections/{collection_id}/overview")
async def get_collection_overview(
    request: Request,
    collection_id: UUID,
    project_id: UUID,
):
    return await handlers.get_collection_overview(request, collection_id, project_id)


@router.post("/collections/{collection_id}/vector-preview")
async def preview_vector_snapshot(request: Request, collection_id: UUID):
    return await handlers.preview_vector_snapshot(request, collection_id)


@router.post("/collections/{collection_id}/vector-snapshots", status_code=202)
async def create_vector_snapshot(request: Request, collection_id: UUID):
    return await handlers.create_vector_snapshot(request, collection_id)


@router.get("/collections/{collection_id}/vector-snapshots")
async def list_vector_snapshots(
    request: Request,
    collection_id: UUID,
    project_id: UUID,
):
    return await handlers.list_vector_snapshots(request, collection_id, project_id)


@router.get("/vector-snapshots/{snapshot_id}")
async def get_vector_snapshot(
    request: Request,
    snapshot_id: UUID,
    project_id: UUID | None = None,
):
    return await handlers.get_vector_snapshot(request, snapshot_id, project_id)

