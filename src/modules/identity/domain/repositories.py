from abc import ABC, abstractmethod
from uuid import UUID

from modules.identity.domain.entities import User, UserInvite, UserSession
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


class UserInviteRepository(ABC):
    @abstractmethod
    async def save(self, invite: UserInvite) -> UserInvite: ...

    @abstractmethod
    async def get_by_id(self, invite_id: UUID) -> UserInvite | None: ...

    @abstractmethod
    async def get_by_workspace_and_email(
        self, workspace_id: UUID, email: str
    ) -> UserInvite | None: ...

    @abstractmethod
    async def list_by_workspace(self, workspace_id: UUID) -> list[UserInvite]: ...

    @abstractmethod
    async def delete(self, invite_id: UUID) -> None: ...


class UserSessionRepository(ABC):
    @abstractmethod
    async def save(self, session: UserSession) -> UserSession: ...

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> UserSession | None: ...

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[UserSession]: ...

    @abstractmethod
    async def paginate_by_user(
        self, user_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UserSession]: ...

    @abstractmethod
    async def delete(self, session_id: UUID) -> None: ...
