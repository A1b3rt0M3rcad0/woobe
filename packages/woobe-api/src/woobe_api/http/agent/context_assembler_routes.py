from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from modules.agent.entrypoint import list_context_assemblers


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


class ContextAssemblerDescriptorResponse(BaseModel):
    """HTTP contract for backend-owned Context Manager presentation metadata."""

    name: str
    version: str
    display_name: str
    description: str
    behavior: str
    is_default: bool


class ContextAssemblerCatalogResponse(BaseModel):
    success: Literal[True] = True
    message: str = "ok"
    data: list[ContextAssemblerDescriptorResponse]


@router.get(
    "/context-assemblers",
    response_model=ContextAssemblerCatalogResponse,
)
async def context_assemblers() -> ContextAssemblerCatalogResponse:
    return ContextAssemblerCatalogResponse(
        data=[
            ContextAssemblerDescriptorResponse.model_validate(item)
            for item in list_context_assemblers()
        ]
    )
