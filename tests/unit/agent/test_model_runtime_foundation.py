import asyncio
from types import SimpleNamespace

import pytest

from modules.agent.application.interfaces.execution_strategy import (
    STANDARD_EXECUTION_COMPATIBILITY,
)
from modules.agent.application.interfaces.model_compatibility import (
    ModelExecutionCompatibilityResolver,
    RuntimeCompatibilityRequest,
)
from modules.agent.application.interfaces.model_output import (
    EmbeddingModelOutputStrategy,
    TextModelOutputStrategy,
)
from modules.agent.application.interfaces.model_runtime import (
    ModelOutput,
    ModelRequest,
    ModelResult,
)
from modules.agent.application.interfaces.model_spec_compatibility import (
    LegacyModelSpecResolver,
)
from modules.agent.application.interfaces.provider_registry import (
    ProviderConnection,
    ProviderManifest,
    ProviderRegistry,
)
from modules.agent.application.use_cases.ai_provider_model_cases import (
    _apply_model_spec_overrides,
)
from modules.agent.domain.model_spec import (
    ModelCapability,
    ModelCapabilityNames,
    ModelInteractionSpec,
    ModelModalities,
    ModelOperations,
    ModelSpec,
    ModelTypes,
    model_spec_hash,
)
from modules.agent.infra.models.embedding_execution import (
    EmbeddingExecutionRequest,
    EmbeddingExecutionStrategy,
)
from modules.agent.infra.models.operation_strategies import EmbeddingModelStrategy


def _embedding_spec() -> ModelSpec:
    return ModelSpec(
        provider="test",
        model_id="embed-v1",
        display_name="Embed V1",
        model_type=ModelTypes.EMBEDDING,
        operations=frozenset({ModelOperations.EMBEDDING_CREATE}),
        input_modalities=frozenset({ModelModalities.TEXT}),
        output_modalities=frozenset({ModelModalities.EMBEDDING}),
        interaction=ModelInteractionSpec(
            mode="isolated",
            supports_batch=True,
        ),
        default_model_strategy=ModelOperations.EMBEDDING_CREATE,
    )


def test_model_spec_round_trip_and_hash_are_deterministic() -> None:
    spec = ModelSpec(
        provider="openai",
        model_id="language-v1",
        display_name="Language V1",
        model_type=ModelTypes.LANGUAGE,
        operations=frozenset({ModelOperations.LANGUAGE_GENERATE}),
        input_modalities=frozenset({ModelModalities.TEXT, ModelModalities.IMAGE}),
        output_modalities=frozenset({ModelModalities.TEXT}),
        interaction=ModelInteractionSpec(
            mode="conversation",
            supports_conversation=True,
            supports_history=True,
            supports_system_instruction=True,
            supports_context_injection=True,
        ),
        capabilities={
            ModelCapabilityNames.TOOL_CALLING: ModelCapability(
                supported=True,
                config={"parallel": True},
                source="provider",
            )
        },
        pricing={"input_cost_per_1m_tokens": 1.0},
    )

    restored = ModelSpec.from_dict(spec.as_dict())

    assert restored == spec
    assert model_spec_hash(restored) == model_spec_hash(spec)


def test_legacy_model_spec_resolver_contains_embedding_name_inference() -> None:
    legacy = SimpleNamespace(
        id=None,
        provider_credential_id=None,
        name="Text Embedding",
        model="text-embedding-3-small",
        metadata={},
    )

    spec = LegacyModelSpecResolver().resolve(legacy, provider="openai")

    assert spec.source == "legacy"
    assert spec.model_type == ModelTypes.EMBEDDING
    assert spec.operations == frozenset({ModelOperations.EMBEDDING_CREATE})
    assert spec.output_modalities == frozenset({ModelModalities.EMBEDDING})
    assert spec.interaction.supports_conversation is False


def test_standard_compatibility_rejects_embedding_semantics() -> None:
    report = ModelExecutionCompatibilityResolver().resolve(
        RuntimeCompatibilityRequest(
            model=_embedding_spec(),
            execution=STANDARD_EXECUTION_COMPATIBILITY,
            context_enabled=True,
            required_input_modalities=frozenset({ModelModalities.TEXT}),
            required_output_modalities=frozenset({ModelModalities.TEXT}),
        )
    )

    codes = {issue.code for issue in report.errors}
    assert report.compatible is False
    assert "operation_not_supported" in codes
    assert "conversation_not_supported" in codes
    assert "execution_output_modality_not_supported" in codes
    assert "model_output_modality_not_supported" in codes


def test_provider_registry_supports_aliases_without_provider_branching() -> None:
    class TestProvider:
        manifest = ProviderManifest(
            key="openai_compatible",
            display_name="OpenAI Compatible",
            supports_discovery=True,
        )

        async def validate_connection(self, connection: ProviderConnection) -> None:
            assert connection.provider == "openai_compatible"

        async def discover_models(
            self,
            connection: ProviderConnection,
        ) -> tuple[ModelSpec, ...]:
            return ()

    provider = TestProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    registry.register_alias("custom", "openai_compatible")

    assert registry.canonical_key("custom") == "openai_compatible"
    assert registry.resolve("custom") is provider
    assert registry.contains("custom") is True


def test_embedding_execution_has_no_conversation_context_knowledge_or_tools() -> None:
    spec = _embedding_spec()

    class Runtime:
        @property
        def spec(self) -> ModelSpec:
            return spec

        async def invoke(self, request: ModelRequest) -> ModelResult:
            assert request.operation == ModelOperations.EMBEDDING_CREATE
            assert request.context is None
            assert request.tools == ()
            return ModelResult(
                outputs=(
                    ModelOutput(
                        modality=ModelModalities.EMBEDDING,
                        value=[0.1, 0.2, 0.3],
                    ),
                )
            )

    execution = EmbeddingExecutionStrategy(
        operation_strategy=EmbeddingModelStrategy(),
    )
    result = asyncio.run(
        execution.execute(
            runtime=Runtime(),
            request=EmbeddingExecutionRequest(texts=("hello",)),
        )
    )

    assert result.runtime_plan.context_strategy is None
    assert result.runtime_plan.knowledge_strategy is None
    assert result.runtime_plan.tools_enabled is False
    assert result.runtime_plan.output_strategy == "embedding"


def test_output_validation_is_modality_aware() -> None:
    result = ModelResult(
        outputs=(
            ModelOutput(
                modality=ModelModalities.EMBEDDING,
                value=[1.0, 2.0],
            ),
        )
    )

    EmbeddingModelOutputStrategy().validate(result)
    with pytest.raises(ValueError, match="text output"):
        TextModelOutputStrategy().validate(result)


def test_manual_provider_model_overrides_update_normalized_spec() -> None:
    spec = ModelSpec(
        provider="openai",
        model_id="language-v1",
        display_name="Language V1",
        model_type=ModelTypes.LANGUAGE,
        operations=frozenset({ModelOperations.LANGUAGE_GENERATE}),
        input_modalities=frozenset({ModelModalities.TEXT}),
        output_modalities=frozenset({ModelModalities.TEXT}),
        interaction=ModelInteractionSpec(
            mode="conversation",
            supports_conversation=True,
        ),
        capabilities={
            ModelCapabilityNames.TOOL_CALLING: ModelCapability(
                supported=True,
                source="provider",
            ),
        },
    )

    resolved = _apply_model_spec_overrides(
        spec,
        {
            "context_window": 64000,
            "max_output_tokens": 4096,
            "capability_source": "manual",
            "capabilities": {
                "supports_tools": False,
                "supports_json": True,
                "supports_streaming": True,
            },
            "pricing": {
                "input_cost_per_1m_tokens": 0.5,
                "output_cost_per_1m_tokens": 1.5,
                "currency": "USD",
            },
        },
    )

    assert resolved.limits.context_window == 64000
    assert resolved.limits.max_output_tokens == 4096
    assert resolved.capability(ModelCapabilityNames.TOOL_CALLING).supported is False
    assert resolved.capability(ModelCapabilityNames.STRUCTURED_OUTPUT).supported is True
    assert resolved.capability(ModelCapabilityNames.STREAMING).supported is True
    assert resolved.pricing["input_cost_per_1m_tokens"] == 0.5
    assert resolved.pricing["output_cost_per_1m_tokens"] == 1.5


def test_manual_unknown_tool_capability_preserves_legacy_behavior_with_warning() -> None:
    spec = ModelSpec(
        provider="openai_compatible",
        model_id="manual-model",
        display_name="Manual Model",
        model_type=ModelTypes.LANGUAGE,
        operations=frozenset({ModelOperations.LANGUAGE_GENERATE}),
        input_modalities=frozenset({ModelModalities.TEXT}),
        output_modalities=frozenset({ModelModalities.TEXT}),
        interaction=ModelInteractionSpec(
            mode="conversation",
            supports_conversation=True,
            supports_history=True,
            supports_system_instruction=True,
            supports_context_injection=True,
        ),
        source="manual",
    )

    report = ModelExecutionCompatibilityResolver().resolve(
        RuntimeCompatibilityRequest(
            model=spec,
            execution=STANDARD_EXECUTION_COMPATIBILITY,
            tools_enabled=True,
            context_enabled=True,
            required_input_modalities=frozenset({ModelModalities.TEXT}),
            required_output_modalities=frozenset({ModelModalities.TEXT}),
        )
    )

    assert report.compatible is True
    assert [issue.code for issue in report.warnings] == ["model_capability_unknown"]


def test_legacy_chat_provider_registry_is_extensible_without_dispatch_branching() -> None:
    from modules.agent.infra.llm.providers import LegacyChatProviderRegistry

    class Provider:
        def create(self, **kwargs):
            return kwargs["model"]

    registry = LegacyChatProviderRegistry()
    registry.register("example", Provider())
    registry.register_alias("example_alias", "example")

    assert registry.resolve("example").create(model="m") == "m"
    assert registry.resolve("example_alias").create(model="m") == "m"


def test_embedding_provider_registry_supports_aliases_and_extensions() -> None:
    from modules.agent.infra.models.embedding_providers import EmbeddingProviderRegistry

    class Provider:
        def create(self, **kwargs):
            return kwargs["model"]

    registry = EmbeddingProviderRegistry()
    registry.register("example", Provider())
    registry.register_alias("example_alias", "example")

    assert registry.resolve("example").create(model="embed") == "embed"
    assert registry.resolve("example_alias").create(model="embed") == "embed"
