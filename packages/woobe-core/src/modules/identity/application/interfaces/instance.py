from datetime import datetime
from typing import Protocol
from uuid import UUID

from modules.identity.application.instance_types import InstanceState


class InstanceRepository(Protocol):
    async def get_state(self) -> InstanceState: ...

    async def has_active_invite(self, email: str) -> bool: ...

    async def claim_bootstrap(self, now: datetime) -> bool: ...

    async def set_owner(self, owner_user_id: UUID, now: datetime) -> None: ...

    async def find_existing_owner(self, email: str) -> UUID | None: ...

    async def initialize_existing_owner(
        self,
        owner_user_id: UUID,
        now: datetime,
    ) -> bool: ...
