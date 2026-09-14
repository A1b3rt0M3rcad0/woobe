from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from modules.agent.entrypoint import list_rag_strategies


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


class RAGStrategyDescriptorResponse(BaseModel):
    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    is_default: bool


class RAGStrategyCatalogResponse(BaseModel):
    success: Literal[True] = True
    message: str = "ok"
    data: list[RAGStrategyDescriptorResponse]


@router.get(
    "/rag-strategies",
    response_model=RAGStrategyCatalogResponse,
)
async def rag_strategies() -> RAGStrategyCatalogResponse:
    return RAGStrategyCatalogResponse(
        data=[
            RAGStrategyDescriptorResponse.model_validate(item)
            for item in list_rag_strategies()
        ]
    )
