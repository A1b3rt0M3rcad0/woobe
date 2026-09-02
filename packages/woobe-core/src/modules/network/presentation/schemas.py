from pydantic import BaseModel, Field, model_validator


class CreateNetworkRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def normalize(self) -> "CreateNetworkRequest":
        self.name = self.name.strip()
        self.description = self.description.strip()
        if not self.name:
            raise ValueError("Network name cannot be blank")
        return self


class UpdateNetworkMetadataRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def normalize(self) -> "UpdateNetworkMetadataRequest":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Network name cannot be blank")
        if self.description is not None:
            self.description = self.description.strip()
        if self.name is None and self.description is None:
            raise ValueError("At least one Network metadata field is required")
        return self
