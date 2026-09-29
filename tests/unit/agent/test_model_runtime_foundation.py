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
