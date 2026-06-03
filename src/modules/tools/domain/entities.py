from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType


@dataclass
class Tool:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    agent_id: UUID | None = None
    name: str = ""
    description: str | None = None
    type: ToolType = ToolType.FUNCTION
    config: dict | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    timeout_ms: int | None = None
    status: ToolStatus = ToolStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Secret:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    name: str = ""
    type: SecretType = SecretType.CUSTOM
    encrypted_value: str = ""
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

