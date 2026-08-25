from abc import ABC, abstractmethod
from uuid import UUID

from modules.identity.domain.entities import (
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
    User,
    UserSession,
)
from shared.infra.objects import CursorPage


class UserRepository(ABC):

    @abstractmethod
    async def save(self, user: User) -> User: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def delete(self, user_id: UUID) -> None: ...


class WorkspaceRepository(ABC):

    @abstractmethod
    async def save(self, workspace: Workspace) -> Workspace: ...

    @abstractmethod
    async def get_by_id(self, workspace_id: UUID) -> Workspace | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Workspace | None: ...

    @abstractmethod
    async def list_all(self) -> list[Workspace]: ...

    @abstractmethod
    async def delete(self, workspace_id: UUID) -> None: ...


class WorkspaceMemberRepository(ABC):

    @abstractmethod
    async def save(self, member: WorkspaceMember) -> WorkspaceMember: ...

    @abstractmethod
    async def get_by_id(self, member_id: UUID) -> WorkspaceMember | None: ...

    @abstractmethod
    async def get_by_workspace_and_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember | None: ...

    @abstractmethod
    async def list_by_workspace(
        self, workspace_id: UUID
    ) -> list[WorkspaceMember]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[WorkspaceMember]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[WorkspaceMember]: ...

    @abstractmethod
    async def paginate_by_user(
        self, user_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[WorkspaceMember]: ...

    @abstractmethod
    async def delete(self, member_id: UUID) -> None: ...


class WorkspaceInviteRepository(ABC):

    @abstractmethod
    async def save(self, invite: WorkspaceInvite) -> WorkspaceInvite: ...

    @abstractmethod
    async def get_by_id(self, invite_id: UUID) -> WorkspaceInvite | None: ...

    @abstractmethod
    async def get_by_workspace_and_email(
        self, workspace_id: UUID, email: str
    ) -> WorkspaceInvite | None: ...

    @abstractmethod
    async def list_by_workspace(
        self, workspace_id: UUID
    ) -> list[WorkspaceInvite]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[WorkspaceInvite]: ...

    @abstractmethod
    async def delete(self, invite_id: UUID) -> None: ...


class UserSessionRepository(ABC):

    @abstractmethod
    async def save(self, session: UserSession) -> UserSession: ...

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> UserSession | None: ...

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[UserSession]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_user(
        self, user_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UserSession]: ...

    @abstractmethod
    async def delete(self, session_id: UUID) -> None: ...
