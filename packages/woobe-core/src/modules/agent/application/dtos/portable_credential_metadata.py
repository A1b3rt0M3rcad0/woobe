"""Non-secret provider connection intent needed to reproduce native SDK selection."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.agent.application.portable_authentication import _validate_url


class PortableCredentialMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider_family: str | None = Field(default=None, min_length=1, max_length=64)
    compatibility: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("base_url")
    @classmethod
    def authentication_free_url(cls, value):
        _validate_url(value)
        return value
