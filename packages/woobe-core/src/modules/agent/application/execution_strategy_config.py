from __future__ import annotations

from copy import deepcopy

from modules.agent.application.execution_strategy_registry import (
    DEFAULT_EXECUTION_STRATEGY,
    SUPPORTED_EXECUTION_STRATEGIES,
    list_execution_strategies,
)
from shared.contracts.errors import ValidationError


def execution_strategy_from_runtime_config(value: object) -> str:
    """Return the stable execution strategy selected by an Agent snapshot.

    Historical Agents and Releases did not persist this field. Missing selection is
    therefore permanently defined as ``standard`` rather than following a mutable
    process-wide default.
    """

    if value is None:
        return DEFAULT_EXECUTION_STRATEGY
    if not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")

    raw = value.get("execution_strategy")
    if raw is None:
        return DEFAULT_EXECUTION_STRATEGY
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError("execution_strategy must be a non-empty string")

    strategy = raw.strip().lower()
    if strategy not in SUPPORTED_EXECUTION_STRATEGIES:
        raise ValidationError(f"Unsupported execution strategy: {strategy}")
    return strategy


def canonicalize_execution_strategy_runtime_config(value: object) -> dict:
    """Freeze the explicit strategy selection in a mutable Agent/Release snapshot."""

    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    runtime_config["execution_strategy"] = execution_strategy_from_runtime_config(
        runtime_config
    )
    return runtime_config


__all__ = [
    "DEFAULT_EXECUTION_STRATEGY",
    "SUPPORTED_EXECUTION_STRATEGIES",
    "canonicalize_execution_strategy_runtime_config",
    "execution_strategy_from_runtime_config",
    "list_execution_strategies",
]
