from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InstanceState:
    owner_user_id: UUID | None
    initialized_at: datetime | None
    signup_mode: str
    telemetry_enabled: bool
    user_count: int

    @property
    def initialized(self) -> bool:
        return self.owner_user_id is not None and self.initialized_at is not None
