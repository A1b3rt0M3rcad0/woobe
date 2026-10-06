from typing import Literal
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from modules.agent.entrypoint import list_knowledge_strategies


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


class KnowledgeStrategyDescriptorResponse(BaseModel):
    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    behavior: str = Field(min_length=1)
    recommended_for: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    is_default: bool
    config_schema: dict[str, Any]
    config_schema_version: str


class KnowledgeStrategyCatalogResponse(BaseModel):
    success: Literal[True] = True
    message: str = "ok"
    data: list[KnowledgeStrategyDescriptorResponse]


@router.get(
    "/knowledge-strategies",
    response_model=KnowledgeStrategyCatalogResponse,
)
async def knowledge_strategies() -> KnowledgeStrategyCatalogResponse:
    return KnowledgeStrategyCatalogResponse(
        data=[
            KnowledgeStrategyDescriptorResponse.model_validate(item)
            for item in list_knowledge_strategies()
        ]
    )
