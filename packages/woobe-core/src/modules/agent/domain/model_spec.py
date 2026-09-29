from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


MODEL_SPEC_VERSION = 1


class ModelTypes:
    """Well-known model families.

    Values are strings on purpose: third-party/custom model families do not need a
    core enum change to participate in the runtime.
    """

    LANGUAGE = "language"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    REALTIME = "realtime"
    CUSTOM = "custom"


class ModelOperations:
    LANGUAGE_GENERATE = "language.generate"
    EMBEDDING_CREATE = "embedding.create"
    RERANK = "rerank"
    IMAGE_GENERATE = "image.generate"
    AUDIO_TRANSCRIBE = "audio.transcribe"
    AUDIO_SYNTHESIZE = "audio.synthesize"
    REALTIME_SESSION = "realtime.session"
    VIDEO_GENERATE = "video.generate"


class ModelModalities:
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    EMBEDDING = "embedding"
    SCORES = "scores"
    JEV = "jev"


class ModelCapabilityNames:
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    REASONING = "reasoning"
    BATCH = "batch"
    CITATIONS = "citations"
    CODE_EXECUTION = "code_execution"
    PROMPT_CACHING = "prompt_caching"
    COMPUTER_USE = "computer_use"


@dataclass(frozen=True, slots=True)
class ModelCapability:
    supported: bool
    config: Mapping[str, Any] = field(default_factory=dict)
    source: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", dict(self.config or {}))

    def as_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "config": dict(self.config),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ModelCapability:
        return cls(
            supported=bool(value.get("supported", False)),
            config=(
                dict(value.get("config") or {})
                if isinstance(value.get("config"), Mapping)
                else {}
            ),
            source=(
                str(value["source"])
                if value.get("source") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ModelInteractionSpec:
    """Interaction semantics independent from token limits.

    A model may accept a large token input without being conversational. Context
    Managers therefore key off these semantics rather than context_window alone.
    """

    mode: str
    supports_conversation: bool = False
    supports_history: bool = False
    supports_system_instruction: bool = False
    supports_context_injection: bool = False
    supports_batch: bool = False
    supports_realtime: bool = False

    def __post_init__(self) -> None:
        if not self.mode.strip():
            raise ValueError("Model interaction mode must not be empty")

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "supports_conversation": self.supports_conversation,
            "supports_history": self.supports_history,
            "supports_system_instruction": self.supports_system_instruction,
            "supports_context_injection": self.supports_context_injection,
            "supports_batch": self.supports_batch,
            "supports_realtime": self.supports_realtime,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ModelInteractionSpec:
        return cls(
            mode=str(value.get("mode") or "isolated"),
            supports_conversation=bool(value.get("supports_conversation", False)),
            supports_history=bool(value.get("supports_history", False)),
            supports_system_instruction=bool(
                value.get("supports_system_instruction", False)
            ),
            supports_context_injection=bool(
                value.get("supports_context_injection", False)
            ),
            supports_batch=bool(value.get("supports_batch", False)),
            supports_realtime=bool(value.get("supports_realtime", False)),
        )


@dataclass(frozen=True, slots=True)
class ModelLimits:
    context_window: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_batch_size: int | None = None
    max_input_bytes: int | None = None
    max_output_bytes: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "context_window",
            "max_input_tokens",
            "max_output_tokens",
            "max_batch_size",
            "max_input_bytes",
            "max_output_bytes",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when provided")

    def as_dict(self) -> dict[str, int | None]:
        return {
            "context_window": self.context_window,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_batch_size": self.max_batch_size,
            "max_input_bytes": self.max_input_bytes,
            "max_output_bytes": self.max_output_bytes,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ModelLimits:
        def positive_int(name: str) -> int | None:
            raw = value.get(name)
            if raw is None or isinstance(raw, bool):
                return None
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                return None
            return parsed if parsed > 0 else None

        return cls(
            context_window=positive_int("context_window"),
            max_input_tokens=positive_int("max_input_tokens"),
            max_output_tokens=positive_int("max_output_tokens"),
            max_batch_size=positive_int("max_batch_size"),
            max_input_bytes=positive_int("max_input_bytes"),
            max_output_bytes=positive_int("max_output_bytes"),
        )


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Normalized Woobe semantic description of one provider model.

    Provider-specific payloads stay in metadata. Core runtime compatibility must use
    normalized fields instead of branching on provider/model names.
    """

    provider: str
    model_id: str
    display_name: str
    model_type: str
    operations: frozenset[str]
    input_modalities: frozenset[str]
    output_modalities: frozenset[str]
    interaction: ModelInteractionSpec
    capabilities: Mapping[str, ModelCapability] = field(default_factory=dict)
    limits: ModelLimits = field(default_factory=ModelLimits)
    pricing: Mapping[str, Any] = field(default_factory=dict)
    default_model_strategy: str | None = None
    source: str = "catalog"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    spec_version: int = MODEL_SPEC_VERSION

    def __post_init__(self) -> None:
        for name in ("provider", "model_id", "display_name", "model_type", "source"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"ModelSpec {name} must not be empty")
        if self.spec_version <= 0:
            raise ValueError("ModelSpec version must be positive")
        if not self.operations:
            raise ValueError("ModelSpec must expose at least one operation")
        if not self.input_modalities:
            raise ValueError("ModelSpec must expose at least one input modality")
        if not self.output_modalities:
            raise ValueError("ModelSpec must expose at least one output modality")

        object.__setattr__(
            self,
            "operations",
            frozenset(str(value).strip() for value in self.operations if str(value).strip()),
        )
        object.__setattr__(
            self,
            "input_modalities",
            frozenset(
                str(value).strip()
                for value in self.input_modalities
                if str(value).strip()
            ),
        )
        object.__setattr__(
            self,
            "output_modalities",
            frozenset(
                str(value).strip()
                for value in self.output_modalities
                if str(value).strip()
            ),
        )
        object.__setattr__(self, "capabilities", dict(self.capabilities or {}))
        object.__setattr__(self, "pricing", dict(self.pricing or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def supports_operation(self, operation: str) -> bool:
        return operation in self.operations

    def accepts(self, modality: str) -> bool:
        return modality in self.input_modalities

    def produces(self, modality: str) -> bool:
        return modality in self.output_modalities

    def capability(self, name: str) -> ModelCapability | None:
        return self.capabilities.get(name)

    def supports_capability(self, name: str) -> bool:
        capability = self.capability(name)
        return bool(capability and capability.supported)

    def as_dict(self) -> dict[str, Any]:
        return {
            "spec_version": self.spec_version,
            "provider": self.provider,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "model_type": self.model_type,
            "operations": sorted(self.operations),
            "input_modalities": sorted(self.input_modalities),
            "output_modalities": sorted(self.output_modalities),
            "interaction": self.interaction.as_dict(),
            "capabilities": {
                name: capability.as_dict()
                for name, capability in sorted(self.capabilities.items())
            },
            "limits": self.limits.as_dict(),
            "pricing": dict(self.pricing),
            "default_model_strategy": self.default_model_strategy,
            "source": self.source,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ModelSpec:
        raw_capabilities = value.get("capabilities")
        capabilities: dict[str, ModelCapability] = {}
        if isinstance(raw_capabilities, Mapping):
            for name, raw in raw_capabilities.items():
                if isinstance(raw, Mapping):
                    capabilities[str(name)] = ModelCapability.from_dict(raw)
                elif isinstance(raw, bool):
                    capabilities[str(name)] = ModelCapability(
                        supported=raw,
                        source="legacy",
                    )

        interaction = value.get("interaction")
        limits = value.get("limits")
        return cls(
            spec_version=int(value.get("spec_version") or MODEL_SPEC_VERSION),
            provider=str(value.get("provider") or "unknown"),
            model_id=str(value.get("model_id") or ""),
            display_name=str(
                value.get("display_name")
                or value.get("model_id")
                or ""
            ),
            model_type=str(value.get("model_type") or ModelTypes.CUSTOM),
            operations=frozenset(
                str(item)
                for item in (value.get("operations") or [])
                if str(item).strip()
            ),
            input_modalities=frozenset(
                str(item)
                for item in (value.get("input_modalities") or [])
                if str(item).strip()
            ),
            output_modalities=frozenset(
                str(item)
                for item in (value.get("output_modalities") or [])
                if str(item).strip()
            ),
            interaction=ModelInteractionSpec.from_dict(
                interaction if isinstance(interaction, Mapping) else {}
            ),
            capabilities=capabilities,
            limits=ModelLimits.from_dict(
                limits if isinstance(limits, Mapping) else {}
            ),
            pricing=(
                dict(value.get("pricing") or {})
                if isinstance(value.get("pricing"), Mapping)
                else {}
            ),
            default_model_strategy=(
                str(value["default_model_strategy"])
                if value.get("default_model_strategy")
                else None
            ),
            source=str(value.get("source") or "catalog"),
            metadata=(
                dict(value.get("metadata") or {})
                if isinstance(value.get("metadata"), Mapping)
                else {}
            ),
        )


__all__ = [
    "MODEL_SPEC_VERSION",
    "ModelCapability",
    "ModelCapabilityNames",
    "ModelInteractionSpec",
    "ModelLimits",
    "ModelModalities",
    "ModelOperations",
    "ModelSpec",
    "ModelTypes",
]
