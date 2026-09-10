from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BehaviorSpecification(BaseModel):
    """Versioned semantic instructions; identity remains on the Agent."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    objective: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    allowed_behaviors: list[str] = Field(default_factory=list)
    disallowed_behaviors: list[str] = Field(default_factory=list)
    operating_instructions: str = ""
    response_guidelines: str = ""
    additional_instructions: str = ""

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported Behavior schema version")
        return value

    @field_validator("responsibilities", "allowed_behaviors", "disallowed_behaviors")
    @classmethod
    def normalize_items(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


def canonicalize_behavior_spec(value: dict | BehaviorSpecification) -> dict:
    return BehaviorSpecification.model_validate(value).model_dump()
