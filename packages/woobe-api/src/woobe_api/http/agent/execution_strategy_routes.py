from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from modules.agent.entrypoint import list_execution_strategies


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


class ExecutionStrategyDescriptorResponse(BaseModel):
    """HTTP contract for backend-owned Execution Strategy presentation metadata."""

    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    behavior: str = Field(min_length=1)
    recommended_for: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    is_default: bool


class ExecutionStrategyCatalogResponse(BaseModel):
    success: Literal[True] = True
    message: str = "ok"
    data: list[ExecutionStrategyDescriptorResponse]


@router.get(
    "/execution-strategies",
    response_model=ExecutionStrategyCatalogResponse,
)
async def execution_strategies() -> ExecutionStrategyCatalogResponse:
    return ExecutionStrategyCatalogResponse(
        data=[
            ExecutionStrategyDescriptorResponse.model_validate(item)
            for item in list_execution_strategies()
        ]
    )
