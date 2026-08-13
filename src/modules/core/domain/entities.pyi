from datetime import datetime
from typing import Any
from uuid import UUID


class Workspace:
    id: UUID
    name: str
    slug: str
    status: Any
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class WorkspaceMember:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    status: Any
    joined_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class Project:
    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    status: Any
    data: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class ApiKey:
    id: UUID
    project_id: UUID
    name: str
    key_prefix: str
    key_hash: bytes
    key_version: int
    scopes: list[str]
    status: Any
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_by_user_id: UUID
    rotated_from_id: UUID | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...
