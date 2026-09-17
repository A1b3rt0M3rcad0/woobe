from __future__ import annotations

from typing import Any, TypeVar

from pydantic import ValidationError

from modules.agent.application.strategy_sdk import ExecutionState


StateT = TypeVar("StateT", bound=ExecutionState)


def _legacy_standard_state(cursor: dict[str, Any]) -> dict[str, Any] | None:
    """Translate pre-StateStore Standard cursors during the compatibility window."""

    if not any(
        key in cursor
        for key in (
            "next_phase",
            "round_index",
            "consecutive_failure_rounds",
            "stopped_reason",
        )
    ):
        return None

    return {
        "phase": cursor.get("next_phase"),
        "tool_round": max(0, int(cursor.get("round_index") or 0)),
        "consecutive_failures": max(
            0,
            int(cursor.get("consecutive_failure_rounds") or 0),
        ),
        "stop_reason": cursor.get("stopped_reason"),
    }


class RuntimeStrategyStateStore:
    """Create, serialize and restore Strategy state without algorithm-specific codecs."""

    def create(
        self,
        state_type: type[StateT],
        cursor: dict[str, Any] | None,
        *,
        strategy_name: str,
    ) -> StateT:
        if cursor is None:
            return state_type()

        payload = cursor.get("state")
        if not isinstance(payload, dict) and strategy_name == "standard":
            try:
                payload = _legacy_standard_state(cursor)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Execution Strategy legacy recovery state is invalid") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Execution Strategy recovery checkpoint is missing state")

        try:
            return state_type.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError("Execution Strategy recovery state is invalid") from exc

    def dump(self, state: ExecutionState) -> dict[str, Any]:
        return state.model_dump(mode="json")
