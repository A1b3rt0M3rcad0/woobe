from __future__ import annotations

from copy import deepcopy

from modules.agent.application.knowledge_strategy_registry import (
    DEFAULT_KNOWLEDGE_STRATEGY,
    SUPPORTED_KNOWLEDGE_STRATEGIES,
)
from shared.contracts.errors import ValidationError


def knowledge_strategy_from_runtime_config(value: object) -> str:
    """Return the stable Knowledge Strategy selected by an Agent snapshot.

    Historical Agents and Releases did not persist this field. Missing selection is
    therefore permanently defined as the built-in RAG Knowledge Strategy.
    """

    if value is None:
        return DEFAULT_KNOWLEDGE_STRATEGY
    if not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")

    raw = value.get("knowledge_strategy")
    if raw is None:
        return DEFAULT_KNOWLEDGE_STRATEGY
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError("knowledge_strategy must be a non-empty string")

    strategy = raw.strip().lower()
    if strategy not in SUPPORTED_KNOWLEDGE_STRATEGIES:
        raise ValidationError(f"Unsupported knowledge strategy: {strategy}")
    return strategy


def canonicalize_knowledge_strategy_runtime_config(value: object) -> dict:
    """Freeze the explicit Knowledge Strategy selection in mutable Agent config."""

    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    runtime_config["knowledge_strategy"] = knowledge_strategy_from_runtime_config(
        runtime_config
    )
    return runtime_config


__all__ = [
    "canonicalize_knowledge_strategy_runtime_config",
    "knowledge_strategy_from_runtime_config",
]
