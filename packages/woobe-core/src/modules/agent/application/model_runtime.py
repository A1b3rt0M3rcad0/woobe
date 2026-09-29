from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from modules.agent.domain.model_spec import ModelSpec


@dataclass(frozen=True, slots=True)
class ModelInput:
    modality: str
    value: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.modality.strip():
            raise ValueError("Model input modality must not be empty")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class ModelOutput:
    modality: str
    value: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.modality.strip():
            raise ValueError("Model output modality must not be empty")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    id: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Model Tool call name must not be empty")
        object.__setattr__(self, "arguments", dict(self.arguments or {}))


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """Model-family-neutral usage evidence.

    Existing token-based LLM usage remains representable while audio/image/custom
    model families can add their own metrics without changing this contract.
    """

    metrics: Mapping[str, int | float] = field(default_factory=dict)
    cost_usd: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", dict(self.metrics or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class ModelRequest:
    operation: str
    inputs: tuple[ModelInput, ...]
    parameters: Mapping[str, Any] = field(default_factory=dict)
    tools: tuple[Mapping[str, Any], ...] = ()
    context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("Model request operation must not be empty")
        if not self.inputs:
            raise ValueError("Model request requires at least one input")
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        object.__setattr__(
            self,
            "tools",
            tuple(dict(tool) for tool in self.tools),
        )
        if self.context is not None:
            object.__setattr__(self, "context", dict(self.context))


@dataclass(frozen=True, slots=True)
class ModelResult:
    outputs: tuple[ModelOutput, ...]
    tool_calls: tuple[ModelToolCall, ...] = ()
    finish_reason: str | None = None
    usage: ModelUsage | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def outputs_for(self, modality: str) -> tuple[ModelOutput, ...]:
        return tuple(
            output for output in self.outputs if output.modality == modality
        )

    def has_output(self, modality: str | None = None) -> bool:
        if modality is None:
            return bool(self.outputs)
        return bool(self.outputs_for(modality))


@runtime_checkable
class ModelRuntime(Protocol):
    @property
    def spec(self) -> ModelSpec: ...

    async def invoke(self, request: ModelRequest) -> ModelResult: ...


@runtime_checkable
class ModelOperationStrategy(Protocol):
    """How one semantic model operation is invoked.

    ExecutionStrategy owns workflow orchestration. ModelOperationStrategy owns only
    operation-level model invocation semantics.
    """

    key: str

    def supports(self, spec: ModelSpec) -> bool: ...

    async def invoke(
        self,
        runtime: ModelRuntime,
        request: ModelRequest,
    ) -> ModelResult: ...


class ModelOperationStrategyRegistry:
    __slots__ = ("_strategies",)

    def __init__(self) -> None:
        self._strategies: dict[str, ModelOperationStrategy] = {}

    def register(self, strategy: ModelOperationStrategy) -> None:
        key = str(strategy.key).strip()
        if not key:
            raise ValueError("Model operation strategy key must not be empty")
        if key in self._strategies:
            raise ValueError(f"Model operation strategy already registered: {key}")
        self._strategies[key] = strategy

    def resolve(self, key: str) -> ModelOperationStrategy:
        strategy = self._strategies.get(str(key).strip())
        if strategy is None:
            raise ValueError(f"Unknown Model operation strategy: {key}")
        return strategy

    def keys(self) -> frozenset[str]:
        return frozenset(self._strategies)


__all__ = [
    "ModelInput",
    "ModelOperationStrategy",
    "ModelOperationStrategyRegistry",
    "ModelOutput",
    "ModelRequest",
    "ModelResult",
    "ModelRuntime",
    "ModelToolCall",
    "ModelUsage",
]
