from abc import ABC, abstractmethod
from uuid import UUID

from modules.identity.domain.entities import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
    User,
    UserSession,
)
from shared.domain.objects import CursorPage


class UserRepository(ABC):

    @abstractmethod
    async def save(self, user: User) -> User: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def delete(self, user_id: UUID) -> None: ...


class OrganizationRepository(ABC):

    @abstractmethod
    async def save(self, organization: Organization) -> Organization: ...

    @abstractmethod
    async def get_by_id(self, organization_id: UUID) -> Organization | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Organization | None: ...

    @abstractmethod
    async def list_all(self) -> list[Organization]: ...

    @abstractmethod
    async def delete(self, organization_id: UUID) -> None: ...


class OrganizationMemberRepository(ABC):

    @abstractmethod
    async def save(self, member: OrganizationMember) -> OrganizationMember: ...

    @abstractmethod
    async def get_by_id(self, member_id: UUID) -> OrganizationMember | None: ...

    @abstractmethod
    async def get_by_organization_and_user(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMember | None: ...

    @abstractmethod
    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[OrganizationMember]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[OrganizationMember]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_organization(
        self, organization_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[OrganizationMember]: ...

    @abstractmethod
    async def paginate_by_user(
        self, user_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[OrganizationMember]: ...

    @abstractmethod
    async def delete(self, member_id: UUID) -> None: ...


class OrganizationInviteRepository(ABC):

    @abstractmethod
    async def save(self, invite: OrganizationInvite) -> OrganizationInvite: ...

    @abstractmethod
    async def get_by_id(self, invite_id: UUID) -> OrganizationInvite | None: ...

    @abstractmethod
    async def get_by_organization_and_email(
        self, organization_id: UUID, email: str
    ) -> OrganizationInvite | None: ...

    @abstractmethod
    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[OrganizationInvite]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_organization(
        self, organization_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[OrganizationInvite]: ...

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
