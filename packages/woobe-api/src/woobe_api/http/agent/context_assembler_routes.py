from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from modules.agent.entrypoint import SETTINGS, list_context_managers


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


class ContextManagerDescriptorResponse(BaseModel):
    """HTTP contract for backend-owned Context Manager presentation metadata."""

    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    behavior: str = Field(min_length=1)
    recommended_for: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    configuration: str = Field(min_length=1)
    supports_skills: bool = False
    is_default: bool


class ContextManagerCatalogResponse(BaseModel):
    success: Literal[True] = True
    message: str = "ok"
    data: list[ContextManagerDescriptorResponse]


@router.get(
    "/context-managers",
    response_model=ContextManagerCatalogResponse,
)
@router.get(
    "/context-assemblers",
    response_model=ContextManagerCatalogResponse,
    include_in_schema=False,
)
async def context_managers() -> ContextManagerCatalogResponse:
    return ContextManagerCatalogResponse(
        data=[
            ContextManagerDescriptorResponse.model_validate(item)
            for item in list_context_managers(SETTINGS.default_context_manager)
        ]
    )
