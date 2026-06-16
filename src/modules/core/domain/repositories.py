from abc import ABC, abstractmethod
from uuid import UUID

from modules.core.domain.entities import ApiKey, Project
from shared.infra.objects import CursorPage


class ProjectRepository(ABC):

    @abstractmethod
    async def save(self, project: Project) -> Project: ...

    @abstractmethod
    async def get_by_id(self, project_id: UUID) -> Project | None: ...

    @abstractmethod
    async def get_by_organization_and_slug(
        self, organization_id: UUID, slug: str
    ) -> Project | None: ...

    @abstractmethod
    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[Project]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_organization(
        self, organization_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Project]: ...

    @abstractmethod
    async def delete(self, project_id: UUID) -> None: ...


class ApiKeyRepository(ABC):

    @abstractmethod
    async def save(self, api_key: ApiKey) -> ApiKey: ...

    @abstractmethod
    async def get_by_id(self, api_key_id: UUID) -> ApiKey | None: ...

    @abstractmethod
    async def get_by_key_hash(self, key_hash: bytes) -> ApiKey | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[ApiKey]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[ApiKey]: ...

    @abstractmethod
    async def delete(self, api_key_id: UUID) -> None: ...
