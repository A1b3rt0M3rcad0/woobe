from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from modules.network.application.rerun_service import NetworkRerunService
from shared.infra.errors import ConflictError, NotFoundError


router = APIRouter(prefix="/network/executions", tags=["network", "runtime"])


@router.post("/{execution_id}/rerun", status_code=201)
async def rerun_network_execution(
    request: Request,
    execution_id: UUID,
    project_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    service = NetworkRerunService(request.app.state.session_factory)
    try:
        execution = await service.execute(
            execution_id=execution_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
    except NotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": str(exc), "data": None},
        )
    except ConflictError as exc:
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": str(exc), "data": None},
        )
    return {
        "success": True,
        "message": "Network Run rerun accepted",
        "data": {
            "execution_id": str(execution.id),
            "rerun_of_execution_id": str(execution_id),
            "status": execution.status,
        },
    }
