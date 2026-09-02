from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from modules.network.domain.entities import Network


class NetworkDraftRepository(ABC):
    @abstractmethod
    async def get_for_project(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
    ) -> Network | None: ...

    @abstractmethod
    async def save_draft(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        expected_revision: int,
        definition: dict[str, Any],
    ) -> Network | None: ...
