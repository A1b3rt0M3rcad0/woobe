from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from modules.agent.application.dtos.vector_snapshot_dtos import (
    CreateVectorSnapshotInput,
    GetCollectionOverviewInput,
    GetVectorSnapshotInput,
    ListVectorSnapshotsInput,
)
from modules.agent.application.use_cases.vector_snapshot_use_cases import (
    CreateVectorSnapshotUseCase,
    GetCollectionOverviewUseCase,
    GetVectorSnapshotUseCase,
    ListVectorSnapshotsUseCase,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/agent/knowledge", tags=["knowledge", "agent"])


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "data": None},
    )


@router.get("/collections/{collection_id}/overview")
async def get_collection_overview(request: Request, collection_id: UUID, project_id: UUID):
    try:
        input_dto = GetCollectionOverviewInput(project_id=project_id, collection_id=collection_id)
        async with AgentUnitOfWork(request.app.state.session_factory) as uow:
            use_case = GetCollectionOverviewUseCase(
                snapshot_repo=uow.vector_snapshots,
                collection_repo=uow.document_collections,
                document_repo=uow.documents,
            )
            output = await use_case.execute(input_dto)
    except NotFoundError as exc:
        return _error(404, str(exc))
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
        input_dto = CreateVectorSnapshotInput(collection_id=collection_id, **body)
        async with AgentUnitOfWork(request.app.state.session_factory) as uow:
            use_case = CreateVectorSnapshotUseCase(
                snapshot_repo=uow.vector_snapshots,
                collection_repo=uow.document_collections,
                document_repo=uow.documents,
                provider_model_repo=uow.provider_models,
                credential_repo=uow.provider_credentials,
            )
            output = await use_case.execute(input_dto)
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
async def list_vector_snapshots(request: Request, collection_id: UUID, project_id: UUID):
    input_dto = ListVectorSnapshotsInput(project_id=project_id, collection_id=collection_id)
    async with AgentUnitOfWork(request.app.state.session_factory) as uow:
        use_case = ListVectorSnapshotsUseCase(uow.vector_snapshots)
        output = await use_case.execute(input_dto)
    return jsonable_encoder(
        {"success": True, "message": "ok", "data": [item.model_dump() for item in output]}
    )


@router.get("/vector-snapshots/{snapshot_id}")
async def get_vector_snapshot(
    request: Request,
    snapshot_id: UUID,
    project_id: UUID | None = None,
):
    try:
        input_dto = GetVectorSnapshotInput(snapshot_id=snapshot_id, project_id=project_id)
        async with AgentUnitOfWork(request.app.state.session_factory) as uow:
            use_case = GetVectorSnapshotUseCase(uow.vector_snapshots)
            output = await use_case.execute(input_dto)
    except NotFoundError as exc:
        return _error(404, str(exc))
    return jsonable_encoder(
        {"success": True, "message": "ok", "data": output.model_dump()}
    )
