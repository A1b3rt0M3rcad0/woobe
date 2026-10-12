from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.model_spec_compatibility import LegacyModelSpecResolver
from modules.agent.domain.entities import Agent, ProviderModel, ProviderCredential
from modules.agent.domain.enums import Provider
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver
from shared.contracts.llm_cost import calculate_llm_cost, provider_model_pricing_snapshot


def pricing(**overrides):
    return provider_model_pricing_snapshot(provider_model_id=None, provider_credential_id=None,
        provider='custom', model='test', metadata={'pricing': {
            'input_cost_per_1m_tokens': 1, 'output_cost_per_1m_tokens': 2, **overrides}})


def cost(snapshot, input_tokens=1000, output_tokens=500):
    return calculate_llm_cost(input_tokens=input_tokens, output_tokens=output_tokens, pricing_snapshot=snapshot)


def test_complete_and_zero_prices_are_known():
    assert cost(pricing()) == {'cost_usd': .002, 'cost_status': 'known', 'cost_reason': None}
    assert cost(pricing(input_cost_per_1m_tokens=0, output_cost_per_1m_tokens=0))['cost_usd'] == 0
    assert cost(pricing(input_cost_per_1m_tokens=0, output_cost_per_1m_tokens=0))['cost_status'] == 'known'


@pytest.mark.parametrize('rates', [
    {'input_cost_per_1m_tokens': None}, {'output_cost_per_1m_tokens': None},
    {'input_cost_per_1m_tokens': -1}, {'output_cost_per_1m_tokens': 'NaN'},
    {'input_cost_per_1m_tokens': 'Infinity'}, {'input_cost_per_1m_tokens': '1e999'}, {'currency': 'BRL'}, {'billing_unit': 'per_request'},
])
def test_missing_invalid_or_unsupported_prices_remain_unknown(rates):
    result = cost(pricing(**rates))
    assert result['cost_usd'] is None and result['cost_status'] == 'unknown_pricing'


@pytest.mark.parametrize('input_tokens,output_tokens', [(None, 1), (1, None), (-1, 1), (True, 1), (1.5, 1)])
def test_invalid_usage_is_not_a_known_cost(input_tokens, output_tokens):
    assert cost(pricing(), input_tokens, output_tokens)['cost_status'] == 'unknown_tokens'


@pytest.mark.parametrize('unit,input_rate,output_rate', [('per_token', .000001, .000002), ('per_1k_tokens', .001, .002), ('per_1m_tokens', 1, 2)])
def test_declared_generic_rates_are_normalized(unit, input_rate, output_rate):
    snapshot = provider_model_pricing_snapshot(provider_model_id=None, provider_credential_id=None,
        provider='custom', model='test', metadata={'pricing': {'input': input_rate, 'output': output_rate, 'billing_unit': unit}})
    assert cost(snapshot)['cost_usd'] == .002
    assert snapshot['billing_unit'] == 'per_1m_tokens'


@pytest.mark.asyncio
@pytest.mark.parametrize('fallback', [False, True])
@pytest.mark.parametrize('has_frozen_price', [False, True])
async def test_immutable_model_prices_win_over_changed_live_catalog(fallback, has_frozen_price):
    project = uuid4()
    credential = ProviderCredential(project_id=project, provider=Provider.custom, name='provider', encrypted_secret='test')
    model = ProviderModel(project_id=project, provider_credential_id=credential.id, name='model', model='test',
        metadata={'pricing': {'input_cost_per_1m_tokens': 1, 'output_cost_per_1m_tokens': 2}} if has_frozen_price else {})
    frozen = LegacyModelSpecResolver().resolve(model, provider='custom').as_dict()
    # A ModelSpec may also be imported without any native ProviderModel ID.
    agent = Agent(project_id=project, name='test', provider=Provider.custom, model='test')
    prefix = 'fallback_' if fallback else ''
    if fallback:
        agent.fallback_provider = Provider.custom; agent.fallback_model = 'test'
    agent.settings = {prefix + 'model_spec': frozen, prefix + 'model_spec_frozen': True}
    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)
    resolved = await resolver._resolve_provider_model_refs(SimpleNamespace(provider_models=None), agent)
    snapshot = resolved.settings[prefix + 'model_pricing']
    assert cost(snapshot)['cost_status'] == ('known' if has_frozen_price else 'unknown_pricing')
    if has_frozen_price:
        assert cost(snapshot)['cost_usd'] == .002
    model.metadata = {'pricing': {'input_cost_per_1m_tokens': 999, 'output_cost_per_1m_tokens': 999}}
    resolver._set_pricing_snapshot(agent, key=prefix + 'model_pricing', provider_model=model, provider=Provider.custom)
    assert agent.settings[prefix + 'model_pricing'] == snapshot


def test_legacy_frozen_metadata_is_read_without_repricing_history():
    model = ProviderModel(project_id=uuid4(), name='model', model='test', metadata={'pricing': {'input': 1, 'output': 2}})
    frozen = LegacyModelSpecResolver().resolve(model, provider='custom').as_dict()
    frozen['pricing'] = {}  # Releases produced before explicit pricing in ModelSpec.
    agent = Agent(project_id=model.project_id, name='test', provider=Provider.custom, model='test', settings={'model_spec': frozen, 'model_spec_frozen': True})
    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)
    resolver._restore_frozen_pricing(agent)
    assert cost(agent.settings['model_pricing'])['cost_usd'] == .002
    frozen['metadata'] = {}
    agent.settings['model_spec'] = frozen
    resolver._restore_frozen_pricing(agent)
    assert cost(agent.settings['model_pricing'])['cost_status'] == 'unknown_pricing'


def test_native_model_spec_prices_are_used_even_without_duplicate_metadata():
    model = ProviderModel(project_id=uuid4(), name='model', model='test', metadata={'pricing': {'input': 1, 'output': 2}})
    model.spec = LegacyModelSpecResolver().resolve(model, provider='custom').as_dict()
    model.metadata = {}
    agent = Agent(project_id=model.project_id, name='test', provider=Provider.custom, model='test')
    ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._set_pricing_snapshot(agent, key='model_pricing', provider_model=model, provider=Provider.custom)
    assert cost(agent.settings['model_pricing'])['cost_usd'] == .002


def test_legacy_release_without_frozen_model_does_not_reuse_draft_cost():
    agent = Agent(project_id=uuid4(), name='test', provider=Provider.custom, model='test', settings={'model_pricing': pricing(), 'model_pricing_frozen': True})
    ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._restore_frozen_pricing(agent)
    assert cost(agent.settings['model_pricing'])['cost_status'] == 'unknown_pricing'
