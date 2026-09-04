from fastapi import APIRouter

from modules.agent.entrypoint import list_context_assemblers


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


@router.get("/context-assemblers")
async def context_assemblers():
    return list_context_assemblers()
