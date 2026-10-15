from copy import deepcopy
from dataclasses import replace

import pytest

from modules.agent.application.model_spec_overrides import compose_model_spec
from modules.agent.domain.model_spec import effective_model_semantic_fingerprint, model_spec_hash
from shared.contracts.errors import ValidationError
from tests.unit.agent.test_model_provider_runtime_regressions import _language_spec


def test_override_inherit_unknown_zero_and_repeat_are_distinct():
    baseline = _language_spec()
    metadata = {'model_spec_overrides': {'capabilities': {'tool_calling': False},
        'pricing': {'input_cost_per_1m_tokens': 0}, 'limits': {'context_window': 100}}}
    effective = compose_model_spec(baseline, metadata)
    assert effective.capability('tool_calling').supported is False
    assert effective.pricing['input_cost_per_1m_tokens'] == 0
    assert model_spec_hash(compose_model_spec(effective, deepcopy(metadata))) == model_spec_hash(effective)
    inherited = {'model_spec_overrides': {'capabilities': {'tool_calling': {'action': 'inherit'}},
        'limits': {'context_window': {'action': 'clear'}}}}
    restored = compose_model_spec(effective, inherited, previous_metadata=metadata)
    assert restored.capability('tool_calling').supported is True
    assert restored.limits.context_window is None
    unknown = compose_model_spec(baseline, {'model_spec_overrides': {'capabilities': {'tool_calling': 'unknown'}}})
    assert unknown.capability('tool_calling') is None


@pytest.mark.parametrize('value', [0, -1, True, float('nan'), '10'])
def test_invalid_limit_is_rejected(value):
    with pytest.raises(ValidationError):
        compose_model_spec(_language_spec(), {'model_spec_overrides': {'limits': {'context_window': value}}})


def test_exact_hash_and_semantic_fingerprint_have_separate_purposes():
    spec = _language_spec()
    cosmetic = replace(spec, display_name='Renamed', source='curated', metadata={'provider_model_raw': {'timestamp': 'later'}})
    assert model_spec_hash(spec) != model_spec_hash(cosmetic)
    assert effective_model_semantic_fingerprint(spec) == effective_model_semantic_fingerprint(cosmetic)
    for altered in (replace(spec, pricing={'input_cost_per_1m_tokens': 1}),
            replace(spec, metadata={'dimensions': 1536}), replace(spec, metadata={'protocol': 'other'})):
        assert effective_model_semantic_fingerprint(spec) != effective_model_semantic_fingerprint(altered)
