from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RuntimeContractsValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_output: dict[str, Any] | None
    external_context: dict[str, Any] | None


__all__ = ["RuntimeContractsValidationRequest"]
