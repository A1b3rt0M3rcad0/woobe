from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import uuid6

from modules.core.domain.enums import (
    ApiKeyKind,
    ApiKeyStatus,
    ProjectStatus,
    RuntimeEnvironment,
    RuntimeTargetType,
)


@dataclass
class Project:
    id: UUID = field(default_factory=uuid6.uuid7)
    workspace_id: UUID = field(default_factory=uuid6.uuid7)
    name: str = ""
    slug: str = ""
    status: ProjectStatus = ProjectStatus.active
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ApiKey:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    credential_id: UUID | None = None
    name: str = ""
    description: str | None = None
    key_prefix: str = ""
    key_hash: bytes = b""
    key_version: int = 1
    scopes: list[str] = field(default_factory=list)
    kind: ApiKeyKind = ApiKeyKind.project
    agent_id: UUID | None = None
    target_type: RuntimeTargetType | None = None
    target_id: UUID | None = None
    environment: RuntimeEnvironment | None = None
    interfaces: list[str] = field(default_factory=list)
    status: ApiKeyStatus = ApiKeyStatus.active
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_by_user_id: UUID | None = None
    created_by_control_key_id: UUID | None = None
    rotated_from_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
