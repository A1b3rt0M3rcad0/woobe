from datetime import datetime
from typing import Any
from uuid import UUID


class User:
    id: UUID
    email: str
    password: bytes
    status: Any
    created_at: datetime
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class Workspace:
    id: UUID
    name: str
    slug: str
    status: Any
    created_at: datetime
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class WorkspaceMember:
    id: UUID
    user_id: UUID
    workspace_id: UUID
    role: Any
    status: Any
    joined_at: datetime
    created_at: datetime
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class WorkspaceInvite:
    id: UUID
    workspace_id: UUID
    email: str
    role: Any
    token_hash: str
    invited_by_user_id: UUID
    status: Any
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class UserSession:
    id: UUID
    user_id: UUID
    refresh_token_hash: bytes
    user_agent: str | None
    ip_address: str | None
    status: Any
    revoked_at: datetime | None
    expires_at: datetime
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...
