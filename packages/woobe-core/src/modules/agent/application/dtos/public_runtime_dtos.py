from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shared.contracts.content_parts import ContentPart, normalize_message_parts


class PublicRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(default='', max_length=32_768)
    content_parts: tuple[ContentPart, ...] | None = Field(default=None, max_length=32)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None
    external_context: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize_content(self):
        self.message, _ = normalize_message_parts(self.message, self.content_parts)
        return self


class PublicCreateJobRequest(PublicRunRequest):
    pass
