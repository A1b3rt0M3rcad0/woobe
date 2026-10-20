import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from modules.artifacts.application.contracts.api import Contract, Identifier


Version = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$')]


class ComponentReference(Contract):
    name: Identifier
    version: Version


class LibraryPin(Contract):
    name: Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')]
    version: Version


class ProcessingLimits(Contract):
    max_bytes: int = Field(default=52_428_800, ge=1, le=536_870_912)
    max_pages: int = Field(default=500, ge=1, le=10_000)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    max_blocks: int = Field(default=20_000, ge=1, le=100_000)
    max_output_tokens: int = Field(default=4096, ge=1, le=32768)


class ProcessingParameters(Contract):
    encoding: Literal['auto', 'utf-8', 'utf-8-sig', 'utf-16', 'latin-1'] = 'auto'
    preserve_blank_lines: bool = True
    max_heading_depth: int = Field(default=6, ge=1, le=6)
    json_max_depth: int = Field(default=64, ge=1, le=128)
    csv_dialect: Literal['excel', 'excel-tab', 'unix'] = 'excel'
    csv_max_columns: int = Field(default=256, ge=1, le=1024)
    max_line_chars: int = Field(default=65_536, ge=1, le=1_048_576)
    languages: tuple[Annotated[str, Field(pattern=r'^[A-Za-z]{2,3}(?:[-_][A-Za-z]{2,4})?$')], ...] = Field(default=(), max_length=8)
    ocr_dpi: int = Field(default=150, ge=72, le=300)


class ProcessingModelReference(Contract):
    configuration_key_id: UUID
    configuration_revision: int = Field(ge=1)
    model_id: UUID
    model_revision: int = Field(ge=1)


class ProcessingRecipe(Contract):
    schema_version: Literal['1'] = '1'
    mode: Literal['store_only', 'extract', 'extract_index'] = 'store_only'
    processor: ComponentReference | None = None
    indexer: ComponentReference | None = None
    ocr: ComponentReference | None = None
    enricher: ComponentReference | None = None
    model: ProcessingModelReference | None = None
    libraries: tuple[LibraryPin, ...] = Field(default=(), max_length=32)
    parameters: ProcessingParameters = Field(default_factory=ProcessingParameters)
    limits: ProcessingLimits = Field(default_factory=ProcessingLimits)

    @model_validator(mode='after')
    def validate_pipeline(self):
        if self.mode == 'store_only':
            if any((self.processor, self.indexer, self.ocr, self.enricher, self.model, self.libraries)):
                raise ValueError('Store-only recipes do not execute or pin processing components')
        elif self.processor is None:
            raise ValueError('Extraction requires a versioned processor')
        if (self.mode == 'extract_index') != (self.indexer is not None):
            raise ValueError('Indexed extraction requires exactly one versioned indexer')
        if (self.enricher is None) != (self.model is None):
            raise ValueError('Model enrichment requires a pinned model configuration reference')
        if len({pin.name for pin in self.libraries}) != len(self.libraries):
            raise ValueError('Library names must be pinned exactly once')
        return self

    def fingerprint(self):
        payload = self.model_dump(mode='json')
        payload['libraries'] = sorted(payload['libraries'], key=lambda pin: pin['name'])
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class ProfileCreate(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    revision: int = Field(ge=1, le=9_223_372_036_854_775_807)
    recipe: ProcessingRecipe


class ProfileDefault(Contract):
    expected_version: int = Field(ge=1)
    profile_id: Identifier | None = None
    profile_revision: int | None = Field(default=None, ge=1, le=9_223_372_036_854_775_807)

    @model_validator(mode='after')
    def validate_reference(self):
        if (self.profile_id is None) != (self.profile_revision is None):
            raise ValueError('Default processing profile requires identity and revision together')
        return self


class ProfileView(ProfileCreate):
    project_id: Identifier
    environment: Literal['draft', 'staging', 'production']
    fingerprint: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    ready: bool
    diagnostics: tuple[str, ...] = ()


class ProfilePage(Contract):
    schema_version: Literal['1'] = '1'
    items: tuple[ProfileView, ...]
    has_more: bool
    next_cursor: str | None = None
    truncated: bool = False


class ProcessingSelection(Contract):
    schema_version: Literal['1'] = '1'
    profile: ProfileView | None
    recipe: ProcessingRecipe
    ready: bool
    diagnostics: tuple[str, ...]
    fingerprint: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    mode: Literal['store_only', 'extract', 'extract_index']
