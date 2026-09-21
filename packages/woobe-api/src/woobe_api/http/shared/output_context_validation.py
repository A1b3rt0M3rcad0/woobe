from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RuntimeContractsValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_contract: dict[str, Any] | None = None
    external_context: dict[str, Any] | None = None


__all__ = ["RuntimeContractsValidationRequest"]
