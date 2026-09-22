from __future__ import annotations

from copy import deepcopy

from shared.contracts.errors import ValidationError


DEFAULT_INTERMEDIATE_MESSAGES_ENABLED = False


def intermediate_messages_enabled_from_runtime_config(value: object) -> bool:
    """Return whether one Agent execution publishes durable intermediate messages.

    Historical Agent snapshots predate this setting and therefore retain the
    original final-only behavior.
    """

    if value is None:
        return DEFAULT_INTERMEDIATE_MESSAGES_ENABLED
    if not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")

    execution = value.get("execution")
    if execution is None:
        return DEFAULT_INTERMEDIATE_MESSAGES_ENABLED
    if not isinstance(execution, dict):
        raise ValidationError("runtime_config.execution must be an object")

    raw = execution.get("intermediate_messages")
    if raw is None:
        return DEFAULT_INTERMEDIATE_MESSAGES_ENABLED
    if not isinstance(raw, bool):
        raise ValidationError(
            "runtime_config.execution.intermediate_messages must be a boolean"
        )
    return raw


def canonicalize_execution_runtime_config(value: object) -> dict:
    """Validate execution-scoped runtime settings without backfilling old snapshots."""

    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}

    execution = runtime_config.get("execution")
    if execution is None:
        return runtime_config
    if not isinstance(execution, dict):
        raise ValidationError("runtime_config.execution must be an object")

    normalized_execution = deepcopy(execution)
    if "intermediate_messages" in normalized_execution:
        normalized_execution["intermediate_messages"] = (
            intermediate_messages_enabled_from_runtime_config(runtime_config)
        )
    runtime_config["execution"] = normalized_execution
    return runtime_config


__all__ = [
    "DEFAULT_INTERMEDIATE_MESSAGES_ENABLED",
    "canonicalize_execution_runtime_config",
    "intermediate_messages_enabled_from_runtime_config",
]
