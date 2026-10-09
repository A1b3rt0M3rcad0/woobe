"""Project-owned ASaC lifecycle policy changes require an explicit base."""
from typing import Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ActorIdentity = Annotated[str, StringConstraints(pattern=r"^(user|control):[0-9a-fA-F-]{36}$")]

class ChangeProjectLifecyclePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    expected_generation: int = Field(ge=0, strict=True)
    managed: bool = Field(strict=True)
    production_actors: list[ActorIdentity] = Field(default_factory=list, max_length=128)
    reason: str = Field(min_length=3, max_length=2048)


    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls,value):
        value=value.strip()
        if len(value)<3: raise ValueError("A meaningful audit reason is required")
        return value

    @field_validator("production_actors")
    @classmethod
    def canonical_actors(cls,values):
        actors=[prefix+":"+str(UUID(identifier)) for prefix,identifier in (value.split(":",1) for value in values)]
        if len(set(actors))!=len(actors): raise ValueError("Actor identities must be unique")
        return sorted(actors)
