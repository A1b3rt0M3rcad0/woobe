from datetime import datetime
from typing import Protocol
from uuid import UUID

from modules.identity.application.auth_types import (
    AcceptedWorkspaceInvite,
    IssuedSession,
    SessionRotation,
)
from modules.identity.domain.entities import User, WorkspaceInvite
from modules.identity.domain.enums import MemberRole


class AccessTokenIssuer(Protocol):
    @property
    def ttl_seconds(self) -> int: ...

    def issue(self, *, user_id: UUID, session_id: UUID) -> str: ...


class AuthenticationSessionRepository(Protocol):
    async def issue(
        self,
        *,
        user_id: UUID,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedSession: ...

    async def rotate(
        self,
        *,
        session_id: UUID,
        secret: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> SessionRotation: ...

    async def revoke(
        self,
        *,
        session_id: UUID | None,
        secret: str | None,
    ) -> None: ...

    async def revoke_all(self, user_id: UUID) -> None: ...


class AuthenticationRepository(Protocol):
    async def list_workspaces(self, user_id: UUID) -> list[dict[str, object]]: ...

    async def list_pending_invites(self, email: str) -> list[dict[str, object]]: ...

    async def create_invite(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        email: str,
        role: MemberRole,
        project_ids: list[UUID],
        expires_at: datetime,
        now: datetime,
    ) -> WorkspaceInvite: ...

    async def accept_invite(
        self,
        *,
        user: User,
        invite_id: UUID,
        now: datetime,
    ) -> AcceptedWorkspaceInvite: ...
