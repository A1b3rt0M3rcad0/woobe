from __future__ import annotations

from typing import Any, TypeVar

from pydantic import ValidationError

from modules.agent.application.context_manager_sdk import ContextManagerState


StateT = TypeVar("StateT", bound=ContextManagerState)


class RuntimeContextManagerStateStore:
    """Create, validate and serialize Context Manager algorithm state."""

    def create(
        self,
        state_type: type[StateT],
        value: object,
        *,
        manager_name: str,
    ) -> StateT:
        if not isinstance(value, dict):
            return state_type()
        if value.get("manager_name") != manager_name:
            return state_type()
        payload = value.get("state")
        if not isinstance(payload, dict):
            return state_type()
        try:
            return state_type.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError("Context Manager checkpoint state is invalid") from exc

    def dump(self, state: ContextManagerState) -> dict[str, Any]:
        return state.model_dump(mode="json")
