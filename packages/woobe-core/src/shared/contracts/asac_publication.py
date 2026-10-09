"""Publication names exact server evidence, never a client success flag."""
from uuid import UUID
from pydantic import Field, StrictStr, field_validator
from urllib.parse import urlsplit
from shared.contracts.asac_requests import StrictASaCRequest


class GitPublicationClaim(StrictASaCRequest):
    repository: StrictStr = Field(min_length=1, max_length=512)
    commit: StrictStr = Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")

    @field_validator("repository")
    @classmethod
    def no_credentials_in_repository(cls, value):
        if not value.strip() or any(character.isspace() for character in value):
            raise ValueError("Repository identity cannot be blank or contain whitespace")
        if "://" in value:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Repository URL must use HTTPS without credentials, query or fragment")
        elif value.count("/") != 1 or ":" in value or "@" in value:
            raise ValueError("Use owner/repository or a public HTTPS repository URL")
        return value


class PublishASaCCandidate(StrictASaCRequest):
    operation_id: UUID
    candidate_id: UUID
    evaluation_id: UUID
    reason: StrictStr = Field(min_length=3, max_length=2048)
    git: GitPublicationClaim | None = None

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Publication reason must contain at least three nonblank characters")
        return value


class CancelASaCPublication(StrictASaCRequest):
    reason: StrictStr = Field(min_length=3, max_length=2048)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Cancellation reason must contain at least three nonblank characters")
        return value
