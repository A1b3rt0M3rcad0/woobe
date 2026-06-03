from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType


class CreateToolInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    type: ToolType = ToolType.FUNCTION
    config: dict | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    timeout_ms: int | None = None


class CreateToolOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    name: str
    description: str | None
    type: ToolType
    config: dict | None
    input_schema: dict | None
    output_schema: dict | None
    risk_level: RiskLevel
    timeout_ms: int | None
    status: ToolStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateSecretInput(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    type: SecretType = SecretType.CUSTOM
    value: str = Field(..., min_length=1)
    data: dict | None = None


class CreateSecretOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    type: SecretType
    data: dict | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

