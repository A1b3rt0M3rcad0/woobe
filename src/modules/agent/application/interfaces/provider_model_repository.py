from abc import ABC, abstractmethod
from uuid import UUID

from modules.agent.domain.entities import ProviderModel
from shared.contracts.pagination import CursorPage


class ProviderModelRepository(ABC):
    @abstractmethod
    async def save(self, provider_model: ProviderModel) -> ProviderModel: ...

    @abstractmethod
    async def get_by_id(self, provider_model_id: UUID) -> ProviderModel | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[ProviderModel]: ...

    @abstractmethod
    async def list_by_credential(self, credential_id: UUID) -> list[ProviderModel]: ...

    @abstractmethod
    async def paginate_by_project(
        self,
        project_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> CursorPage[ProviderModel]: ...

    @abstractmethod
    async def update(self, provider_model: ProviderModel) -> ProviderModel: ...

    @abstractmethod
    async def delete(self, provider_model_id: UUID) -> None: ...
