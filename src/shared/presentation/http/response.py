from typing import Any

from pydantic import BaseModel, Field


class Response(BaseModel):
    status_code: int
    body: Any = None
    headers: dict[str, Any] = Field(default_factory=dict)
