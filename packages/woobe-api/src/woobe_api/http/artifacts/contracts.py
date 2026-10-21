from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from modules.artifacts.entrypoint import Action


Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$')]


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class FileCreate(Body):
    operation_id: Identifier
    kind: Literal['text', 'directory']
    path: str = Field(min_length=1, max_length=1024)
    text: str | None = Field(default=None, max_length=262144)

    @model_validator(mode='after')
    def validate_kind(self):
        if (self.kind == 'text') != (self.text is not None):
            raise ValueError('Text files require text; directories do not accept content')
        return self


class FileMove(Body):
    operation_id: Identifier
    expected_version: int = Field(ge=1)
    path: str = Field(min_length=1, max_length=1024)


class TextUpdate(Body):
    operation_id: Identifier
    expected_revision: Identifier
    path: str = Field(min_length=1, max_length=1024)
    text: str = Field(max_length=262144)


class GrantCreate(Body):
    subject_id: Identifier
    actions: frozenset[Action] = Field(min_length=1)
    artifact_workspace_id: Identifier | None = None
    external_namespace: str | None = Field(default=None, min_length=1, max_length=255)
    expires_at: AwareDatetime | None = None

    @model_validator(mode='after')
    def validate_selector(self):
        if (self.artifact_workspace_id is None) == (self.external_namespace is None):
            raise ValueError('Grant requires exactly one Workspace or namespace selector')
        return self
