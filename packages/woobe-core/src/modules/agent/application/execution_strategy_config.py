from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from shared.contracts.errors import ValidationError


DEFAULT_EXECUTION_STRATEGY = "standard"


@dataclass(frozen=True, slots=True)
class ExecutionStrategyDescriptor:
    """Backend-owned product metadata for one selectable Agent execution algorithm."""

    name: str
    display_name: str
    description: str
    behavior: str
    recommended_for: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    is_default: bool = False

    def __post_init__(self) -> None:
        required_text = {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"Execution Strategy descriptor {field_name} must not be empty"
                )

        required_lists = {
            "recommended_for": self.recommended_for,
            "capabilities": self.capabilities,
            "limitations": self.limitations,
        }
        for field_name, values in required_lists.items():
            if not values or any(not item.strip() for item in values):
                raise ValueError(
                    f"Execution Strategy descriptor {field_name} must contain non-empty values"
                )

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "recommended_for": list(self.recommended_for),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "is_default": self.is_default,
        }


_EXECUTION_STRATEGY_DESCRIPTORS = (
    ExecutionStrategyDescriptor(
        name="standard",
        display_name="Standard",
        description=(
            "General-purpose Woobe execution strategy for model and capability orchestration."
        ),
        behavior=(
            "Invokes the configured model, executes bound capabilities when requested, "
            "feeds durable results back into the model, and continues until terminal output "
            "or runtime safety limits are reached."
        ),
        recommended_for=(
            "General-purpose Agents that need predictable production behavior.",
            "Agents that use Tools, Knowledge, structured output, or multi-round capability calls.",
        ),
        capabilities=(
            "Single-pass and multi-round Model execution.",
            "Parallel Tool calls within one capability round.",
            "Durable Tool-boundary recovery without replaying completed Tool side effects.",
            "Structured output validation and JSON repair.",
        ),
        limitations=(
            "Does not add an explicit planning or reflection phase beyond model-directed capability use.",
        ),
        is_default=True,
    ),
)

SUPPORTED_EXECUTION_STRATEGIES = frozenset(
    descriptor.name for descriptor in _EXECUTION_STRATEGY_DESCRIPTORS
)


def list_execution_strategies() -> list[dict[str, object]]:
    """Return backend-owned metadata for every selectable execution strategy."""

    return [
        descriptor.as_dict()
        for descriptor in sorted(
            _EXECUTION_STRATEGY_DESCRIPTORS,
            key=lambda descriptor: (
                0 if descriptor.is_default else 1,
                descriptor.display_name.lower(),
                descriptor.name,
            ),
        )
    ]


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
