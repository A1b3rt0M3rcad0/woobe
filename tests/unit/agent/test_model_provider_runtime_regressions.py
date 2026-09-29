from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
)
from modules.agent.application.interfaces.execution_strategy import (
    STANDARD_EXECUTION_COMPATIBILITY,
)
from modules.agent.application.interfaces.model_compatibility import (
    ModelExecutionCompatibilityResolver,
    RuntimeCompatibilityRequest,
)
from modules.agent.application.interfaces.model_runtime import (
    ModelInput,
    ModelRequest,
)
from modules.agent.application.interfaces.model_spec_compatibility import (
    LegacyModelSpecResolver,
)
from modules.agent.application.interfaces.provider_registry import ProviderConnection
from modules.agent.domain.entities import AgentRelease, ProviderModel
from modules.agent.domain.enums import ProviderModelStatus, ReleaseStatus
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
from modules.agent.infra.adapters import model_provider_registry
from modules.agent.infra.adapters.model_provider_registry import (
    AnthropicProviderAdapter,
    DeepSeekProviderAdapter,
    OpenAICompatibleProviderAdapter,
    OpenAIProviderAdapter,
    OpenRouterProviderAdapter,
    build_provider_registry,
)
from modules.agent.infra.database.mappers import (
    agent_release_entity_to_model,
    agent_release_model_to_entity,
)
from modules.agent.infra.database.provider_model_repositories import (
    _to_entity as provider_model_to_entity,
    _to_model as provider_model_to_model,
)
from modules.agent.infra.models.legacy_model_runtime import (
    LangChainLanguageModelRuntime,
)


def _language_spec(
    *,
    source: str = "provider",
    tools: bool | None = True,
) -> ModelSpec:
    capabilities = {}
    if tools is not None:
        capabilities[ModelCapabilityNames.TOOL_CALLING] = ModelCapability(
            supported=tools,
            source=source,
        )
    return ModelSpec(
        provider="openai",
        model_id="gpt-test",
        display_name="GPT Test",
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
        capabilities=capabilities,
        source=source,
    )


@pytest.mark.parametrize(
    ("context_enabled", "tools_enabled", "tools_supported", "compatible", "code"),
    [
        (True, False, True, True, None),
        (False, False, True, False, "context_required"),
        (True, True, False, False, "model_capability_not_supported"),
        (True, True, None, True, "model_capability_unknown"),
    ],
)
def test_model_execution_compatibility_matrix(
    context_enabled,
    tools_enabled,
    tools_supported,
    compatible,
    code,
):
    source = "legacy" if tools_supported is None else "provider"
    report = ModelExecutionCompatibilityResolver().resolve(
        RuntimeCompatibilityRequest(
            model=_language_spec(source=source, tools=tools_supported),
            execution=STANDARD_EXECUTION_COMPATIBILITY,
            context_enabled=context_enabled,
            tools_enabled=tools_enabled,
            required_input_modalities=frozenset({ModelModalities.TEXT}),
            required_output_modalities=frozenset({ModelModalities.TEXT}),
        )
    )

    assert report.compatible is compatible
    if code:
        assert code in {issue.code for issue in report.issues}


def test_legacy_persisted_language_shape_preserves_explicit_runtime_metadata():
    legacy = SimpleNamespace(
        id=uuid4(),
        provider_credential_id=uuid4(),
        name="Legacy Chat",
        model="legacy-chat-v1",
        metadata={
            "context_window": 64000,
            "max_output_tokens": 4096,
            "capability_source": "manual",
            "capabilities": {
                "supports_tools": True,
                "supports_json": False,
                "supports_streaming": True,
            },
        },
    )

    spec = LegacyModelSpecResolver().resolve(legacy, provider="custom")

    assert spec.model_type == ModelTypes.LANGUAGE
    assert spec.limits.context_window == 64000
    assert spec.limits.max_output_tokens == 4096
    assert spec.capability(ModelCapabilityNames.TOOL_CALLING).supported is True
    assert spec.capability(ModelCapabilityNames.STRUCTURED_OUTPUT).supported is False
    assert spec.capability(ModelCapabilityNames.STREAMING).supported is True
    assert spec.source == "legacy"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_cls", "provider_key", "discovery_key", "base_url"),
    [
        (OpenAIProviderAdapter, "openai", "openai", None),
        (
            OpenAICompatibleProviderAdapter,
            "openai_compatible",
            "custom",
            "https://models.example/v1",
        ),
        (OpenRouterProviderAdapter, "openrouter", "openrouter", None),
    ],
)
async def test_discovery_service_provider_adapters_normalize_without_shared_dispatch(
    adapter_cls,
    provider_key,
    discovery_key,
    base_url,
):
    calls = []

    class Discovery:
        async def list_models(self, context):
            calls.append(context)
            return [
                AvailableProviderModelOutput(
                    id="model-v1",
                    label="Model V1",
                    provider=discovery_key,
                    context_window=32768,
                    max_output_tokens=4096,
                    supports_tools=True,
                    supports_json=True,
                    supports_streaming=True,
                    raw={
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                )
            ]

    adapter = adapter_cls(Discovery())
    specs = await adapter.discover_models(
        ProviderConnection(
            provider=provider_key,
            api_key="secret",
            base_url=base_url,
        )
    )

    assert calls[0].provider == discovery_key
    if base_url:
        assert calls[0].metadata["base_url"] == base_url
    assert specs[0].provider == provider_key
    assert specs[0].operations == frozenset({ModelOperations.LANGUAGE_GENERATE})
    assert specs[0].limits.context_window == 32768
    assert specs[0].supports_capability(ModelCapabilityNames.TOOL_CALLING)


def test_provider_registry_exposes_all_first_class_providers_and_custom_alias():
    registry = build_provider_registry()

    assert registry.keys() == frozenset(
        {"openai", "openai_compatible", "openrouter", "anthropic", "deepseek"}
    )
    assert registry.canonical_key("custom") == "openai_compatible"
    assert registry.resolve("custom") is registry.resolve("openai_compatible")


@pytest.mark.asyncio
async def test_anthropic_discovery_contract_normalizes_capabilities(monkeypatch):
    captured = {}

    async def fake_json_get(url, *, headers):
        captured.update(url=url, headers=headers)
        return {
            "data": [
                {
                    "id": "claude-test",
                    "display_name": "Claude Test",
                    "max_input_tokens": 200000,
                    "max_tokens": 8192,
                    "capabilities": {
                        "image_input": {"supported": True},
                        "structured_outputs": {"supported": True},
                    },
                }
            ]
        }

    monkeypatch.setattr(model_provider_registry, "_async_json_get", fake_json_get)
    specs = await AnthropicProviderAdapter().discover_models(
        ProviderConnection(provider="anthropic", api_key="secret")
    )

    spec = specs[0]
    assert captured["url"].endswith("/v1/models?limit=1000")
    assert captured["headers"]["X-Api-Key"] == "secret"
    assert spec.provider == "anthropic"
    assert spec.input_modalities == frozenset(
        {ModelModalities.TEXT, ModelModalities.IMAGE}
    )
    assert spec.limits.context_window == 200000
    assert spec.supports_capability(ModelCapabilityNames.STRUCTURED_OUTPUT)


@pytest.mark.asyncio
async def test_deepseek_discovery_contract_normalizes_modalities_and_reasoning(monkeypatch):
    async def fake_json_get(_url, *, headers):
        assert headers["Authorization"] == "Bearer secret"
        return {
            "data": [
                {
                    "id": "deepseek-test",
                    "name": "DeepSeek Test",
                    "input_modalities": ["text", "image"],
                    "output_modalities": ["text"],
                    "context_window": 128000,
                    "max_output_tokens": 8192,
                    "effort": {
                        "supported_levels": ["low", "high"],
                        "default_level": "low",
                    },
                }
            ]
        }

    monkeypatch.setattr(model_provider_registry, "_async_json_get", fake_json_get)
    specs = await DeepSeekProviderAdapter().discover_models(
        ProviderConnection(provider="deepseek", api_key="secret")
    )

    spec = specs[0]
    assert spec.input_modalities == frozenset(
        {ModelModalities.TEXT, ModelModalities.IMAGE}
    )
    assert spec.output_modalities == frozenset({ModelModalities.TEXT})
    assert spec.limits.context_window == 128000
    reasoning = spec.capability(ModelCapabilityNames.REASONING)
    assert reasoning is not None and reasoning.supported is True
    assert reasoning.config["levels"] == ["low", "high"]


def test_provider_model_persistence_mapper_round_trip_preserves_normalized_spec():
    spec = _language_spec()
    entity = ProviderModel(
        project_id=uuid4(),
        provider_credential_id=uuid4(),
        name="GPT Test",
        model="gpt-test",
        model_type=spec.model_type,
        spec=spec.as_dict(),
        spec_version=spec.spec_version,
        spec_hash=model_spec_hash(spec),
        status=ProviderModelStatus.active,
        metadata={"source": "provider_catalog"},
    )

    restored = provider_model_to_entity(provider_model_to_model(entity))

    assert restored.id == entity.id
    assert restored.model_type == ModelTypes.LANGUAGE
    assert restored.spec == spec.as_dict()
    assert restored.spec_version == spec.spec_version
    assert restored.spec_hash == model_spec_hash(spec)
    assert restored.metadata == {"source": "provider_catalog"}


def test_release_persistence_mapper_round_trip_preserves_model_spec_snapshots():
    spec = _language_spec()
    snapshot = spec.as_dict()
    digest = model_spec_hash(spec)
    release = AgentRelease(
        project_id=uuid4(),
        agent_id=uuid4(),
        version="v1",
        status=ReleaseStatus.draft,
        session_mode="stateful",
        model_spec_snapshot=snapshot,
        model_spec_hash=digest,
        fallback_model_spec_snapshot=snapshot,
        fallback_model_spec_hash=digest,
    )

    restored = agent_release_model_to_entity(
        agent_release_entity_to_model(release)
    )

    assert restored.model_spec_snapshot == snapshot
    assert restored.model_spec_hash == digest
    assert restored.fallback_model_spec_snapshot == snapshot
    assert restored.fallback_model_spec_hash == digest


@pytest.mark.asyncio
async def test_langchain_runtime_translates_generic_request_tools_result_and_usage():
    class FakeModel:
        def __init__(self):
            self.bound = None
            self.messages = None

        def bind_tools(self, tools, tool_choice):
            self.bound = (tools, tool_choice)
            return self

        async def ainvoke(self, messages):
            self.messages = messages
            return AIMessage(
                content="done",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "lookup",
                        "args": {"q": "woobe"},
                    }
                ],
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "total_tokens": 12,
                },
                response_metadata={"finish_reason": "tool_calls"},
            )

    model = FakeModel()
    runtime = LangChainLanguageModelRuntime(
        model=model,
        spec=_language_spec(),
    )
    result = await runtime.invoke(
        ModelRequest(
            operation=ModelOperations.LANGUAGE_GENERATE,
            inputs=(
                ModelInput(
                    modality=ModelModalities.TEXT,
                    value="hello",
                ),
            ),
            tools=(
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "parameters": {"type": "object"},
                    },
                },
            ),
            context={"messages": [HumanMessage(content="hello")]},
        )
    )

    assert model.bound is not None
    assert model.bound[1] == "auto"
    assert len(model.messages) == 1
    assert result.outputs_for(ModelModalities.TEXT)[0].value == "done"
    assert result.tool_calls[0].name == "lookup"
    assert result.tool_calls[0].arguments == {"q": "woobe"}
    assert result.finish_reason == "tool_calls"
    assert result.usage is not None
    assert result.usage.metrics["input_tokens"] == 10
    assert result.usage.metrics["output_tokens"] == 2
