"""Backward-compatible typed runtime content for messages and artifact inputs."""

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError as PydanticValidationError,
    field_validator,
    model_validator,
)

from shared.contracts.artifact_reference import ArtifactReference


class ContentPartContract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class TextContentPart(ContentPartContract):
    type: Literal['text'] = 'text'
    text: str = Field(min_length=1, max_length=32_768)


class ArtifactContentPart(ContentPartContract):
    type: Literal['artifact'] = 'artifact'
    ref: ArtifactReference
    media_type_hint: str | None = Field(
        default=None,
        min_length=3,
        max_length=255,
        pattern=r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+(?:;[ -~]+)?$",
    )

    @field_validator('media_type_hint')
    @classmethod
    def validate_media_type_hint(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.isascii()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise ValueError('Invalid Artifact media type hint')
        return value


ContentPart: TypeAlias = Annotated[
    TextContentPart | ArtifactContentPart,
    Field(discriminator='type'),
]


class ContentParts(ContentPartContract):
    parts: tuple[ContentPart, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def validate_budgets(self):
        if sum(len(part.text) for part in self.parts if isinstance(part, TextContentPart)) > 32_768:
            raise ValueError('Combined message text exceeds 32768 characters')
        if sum(isinstance(part, ArtifactContentPart) for part in self.parts) > 16:
            raise ValueError('A message can reference at most 16 Artifacts')
        if not any(
            isinstance(part, ArtifactContentPart)
            or (isinstance(part, TextContentPart) and part.text.strip())
            for part in self.parts
        ):
            raise ValueError('Content parts must contain text or an Artifact reference')
        return self


def normalize_message_parts(message: str | None, parts: tuple[ContentPart, ...] | list[ContentPart] | None
                            ) -> tuple[str, tuple[ContentPart, ...] | None]:
    """Return the legacy text projection and a typed immutable part sequence."""
    text = message if isinstance(message, str) else ''
    if parts is None:
        if not text.strip():
            raise ValueError('A message or content_parts are required')
        return text, (TextContentPart(text=text),)
    if text.strip():
        raise ValueError('Use either the legacy message string or content_parts, not both')
    validated = ContentParts(parts=tuple(parts)).parts
    projection = ''.join(part.text for part in validated if isinstance(part, TextContentPart))
    return projection, validated


def serialize_content_parts(parts: tuple[ContentPart, ...] | list[ContentPart] | None) -> list[dict]:
    """Serialize only typed text and exact Artifact references for durable history."""
    return [part.model_dump(mode='json') for part in (parts or ())]


def serialize_message_content_parts(
    message: str,
    parts: tuple[ContentPart, ...] | list[ContentPart] | None,
) -> list[dict]:
    """Serialize a boundary-validated message, normalizing legacy string input."""
    if parts is None:
        _, normalized = normalize_message_parts(message, None)
        return serialize_content_parts(normalized)
    return serialize_content_parts(ContentParts(parts=tuple(parts)).parts)


def validate_stored_content_parts(value: object) -> list[dict] | None:
    """Validate durable history before attaching it to an internal conversation."""
    if not isinstance(value, (list, tuple)):
        return None
    try:
        return serialize_content_parts(ContentParts(parts=tuple(value)).parts)
    except (PydanticValidationError, TypeError, ValueError):
        return None
