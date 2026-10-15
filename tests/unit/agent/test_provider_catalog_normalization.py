from types import SimpleNamespace

import pytest

from modules.agent.application.interfaces.provider_registry import ProviderConnection, UnclassifiedProviderModel
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryService, _number_or_none
from modules.agent.infra.adapters.model_provider_registry import OpenAIProviderAdapter, OpenAICompatibleProviderAdapter, OpenRouterProviderAdapter, AnthropicProviderAdapter, DeepSeekProviderAdapter, ProviderAdapterError
from modules.agent.infra.adapters.provider_discovery_adapters import _spec_to_available_output
from modules.agent.infra.adapters import model_provider_registry as providers


@pytest.mark.parametrize('raw,operation', [
    ({'type': 'model'}, None),
    ({'input_modalities': ['text'], 'output_modalities': ['text']}, 'language.generate'),
    ({'input_modalities': ['text', 'image'], 'output_modalities': ['text']}, 'language.generate'),
    ({'model_type': 'embedding'}, 'embedding.create'),
    ({'architecture': {'input_modalities': ['text'], 'output_modalities': ['image']}}, 'image.generate'),
    ({'input_modalities': ['text'], 'output_modalities': ['audio']}, 'audio.synthesize'),
])
def test_compatible_classification_uses_evidence_not_slug(raw, operation):
    item = ModelDiscoveryService()._normalize_openai({'data': [{'id': 'anything', **raw}]}, provider='custom')[0]
    spec = OpenAICompatibleProviderAdapter()._normalize_item(item)
    output = _spec_to_available_output(spec, provider='custom')
    assert output.provider == 'openai_compatible'
    if operation is None:
        assert output.model_spec is None and not output.operations
        assert output.normalization_status == 'unclassified'
    else:
        assert output.model_spec == output.raw['woobe_model_spec']
        assert output.operations == [operation]


def test_openai_enrichment_is_exact_and_explicit_false_wins():
    service = ModelDiscoveryService()
    items = service._normalize_openai({'data': [{'id': 'gpt-4o-mini'},
        {'id': 'gpt-4o-mini', 'supports_tools': False}, {'id': 'ft:gpt-4o-mini:unknown'}]}, provider='openai')
    adapter = OpenAIProviderAdapter()
    specs = [adapter._normalize_item(item) for item in items]
    assert specs[0].capability('tool_calling').supported is True
    assert specs[1].capability('tool_calling').supported is False
    assert isinstance(specs[2], UnclassifiedProviderModel)


@pytest.mark.parametrize('value', [True, -1, 'nan', 'inf', '-inf'])
def test_invalid_remote_prices_stay_unknown(value):
    assert _number_or_none(value) is None


@pytest.mark.asyncio
async def test_anthropic_pagination_deduplicates_and_refuses_repeated_cursor(monkeypatch):
    calls = []
    async def fetch(url, *, headers):
        calls.append(url)
        return {'data': [{'id': 'claude-a', 'lifecycle': 'deprecated'}], 'has_more': len(calls) == 1, 'last_id': 'claude-a'}
    monkeypatch.setattr(providers, '_async_json_get', fetch)
    result = await AnthropicProviderAdapter().discover_models(ProviderConnection(provider='anthropic', api_key='fixture'))
    assert len(result) == 1 and 'after_id=claude-a' in calls[1]
    assert result[0].metadata['provider_model_raw']['lifecycle'] == 'deprecated'
    async def stuck(url, *, headers):
        return {'data': [], 'has_more': True, 'last_id': 'same'}
    monkeypatch.setattr(providers, '_async_json_get', stuck)
    with pytest.raises(ProviderAdapterError, match='progress'):
        await AnthropicProviderAdapter().discover_models(ProviderConnection(provider='anthropic', api_key='fixture'))


@pytest.mark.asyncio
async def test_deepseek_preserves_protocol_constraints_without_universal_flags(monkeypatch):
    async def fetch(url, *, headers):
        return {'data': [{'id': 'deepseek-chat', 'api_capabilities': {'anthropic_messages': {'system_prompt_update': 'leading-only'}}}]}
    monkeypatch.setattr(providers, '_async_json_get', fetch)
    spec, = await DeepSeekProviderAdapter().discover_models(ProviderConnection(provider='deepseek', api_key='fixture'))
    assert spec.capability('tool_calling') is None
    assert spec.metadata['runtime_constraints']['anthropic_messages']['system_prompt_update'] == 'leading-only'


@pytest.mark.asyncio
async def test_openrouter_embedding_uses_same_normalizer_and_preserves_price(monkeypatch):
    from modules.agent.infra.adapters import openrouter_embedding_discovery as embeddings
    def fetch(url, key):
        return {'data': [{'id': 'vendor/vector', 'context_length': 8192, 'pricing': {'prompt': '0.00000002'}}]}
    monkeypatch.setattr(embeddings, '_json_get', fetch)
    item, = await embeddings.OpenRouterEmbeddingModelDiscoveryService().list_models(api_key='fixture', metadata={})
    assert item.operations == ['embedding.create']
    assert item.model_spec['limits']['max_input_tokens'] == 8192
    assert item.model_spec['pricing']['input_cost_per_1m_tokens'] == .02
