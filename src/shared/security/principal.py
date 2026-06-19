from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuthenticatedPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    session_id: UUID
    issued_at: datetime
    expires_at: datetime
