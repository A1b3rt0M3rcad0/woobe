from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from modules.agent.entrypoint import SETTINGS, list_context_assemblers


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


class ContextAssemblerDescriptorResponse(BaseModel):
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
            for item in list_context_assemblers(SETTINGS.default_context_manager)
        ]
    )
