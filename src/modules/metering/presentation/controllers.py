from uuid import UUID

from fastapi import APIRouter, Depends, Query

from modules.metering.application.providers import MeteringProviders
from modules.metering.presentation.schemas import (
    DailyUsageResponse,
    RecordUsageRequest,
    UsageEventResponse,
)
from shared.infra.database.session_manager import SessionManager
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, ok

router = APIRouter(prefix="/metering", tags=["metering"])


@router.post("/usage-events", status_code=201)
async def record_usage(
    body: RecordUsageRequest,
    manager: SessionManager = Depends(get_session_manager),
):
    providers = MeteringProviders(manager.session)
    result = await providers.record_usage_use_case().execute(body)
    return created({"event_id": str(result.event_id)})


@router.get("/projects/{project_id}/daily")
async def get_project_daily_usage(
    project_id: UUID,
    limit: int = Query(100),
    offset: int = Query(0),
    manager: SessionManager = Depends(get_session_manager),
):
    providers = MeteringProviders(manager.session)
    items = await providers.get_project_daily_usage_use_case().execute(
        project_id, limit=limit, offset=offset
    )
    return ok([DailyUsageResponse(**item.model_dump()) for item in items])


@router.get("/agents/{agent_id}/daily")
async def get_agent_daily_usage(
    agent_id: UUID,
    limit: int = Query(100),
    offset: int = Query(0),
    manager: SessionManager = Depends(get_session_manager),
):
    providers = MeteringProviders(manager.session)
    items = await providers.get_agent_daily_usage_use_case().execute(
        agent_id, limit=limit, offset=offset
    )
    return ok([DailyUsageResponse(**item.model_dump()) for item in items])
