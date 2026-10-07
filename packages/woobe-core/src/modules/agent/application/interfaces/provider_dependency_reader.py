from typing import Protocol
from uuid import UUID


class ProviderDependencyReader(Protocol):
    async def embedding_consumers(
        self, project_id: UUID, model_ids: set[UUID]
    ) -> list[dict]: ...
