from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import uuid6


@dataclass
class AgentReleaseActivation:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    release_id: UUID = field(default_factory=uuid6.uuid7)
    previous_release_id: UUID | None = None
    action: str = "deploy"
    change_description: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
