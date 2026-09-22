from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContextManagerState(BaseModel):
    """Serializable algorithm state owned by one concrete Context Manager."""

    model_config = ConfigDict(extra="forbid")
