from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ListAvailableProviderModelsInput(BaseModel):
    credential_id: UUID
    project_id: UUID | None = None
    capability: str | None = None


class AvailableProviderModelOutput(BaseModel):
    id: str
    label: str
    provider: str
    source: str = "remote"
    owned_by: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    input_cost_per_1m_tokens: float | None = None
    output_cost_per_1m_tokens: float | None = None
    supports_tools: bool | None = None
    supports_json: bool | None = None
    supports_streaming: bool | None = None
    model_type: str | None = None
    operations: list[str] = []
    input_modalities: list[str] = []
    output_modalities: list[str] = []
    capabilities: dict[str, Any] = {}
    raw: dict[str, Any] = {}
