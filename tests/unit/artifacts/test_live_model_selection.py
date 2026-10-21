import pytest

from tests.support.artifact_model_live import live_model_settings


NAMES = ('WOOBE_ARTIFACT_MODEL_PROVIDER', 'WOOBE_ARTIFACT_MODEL_NAME',
         'WOOBE_ARTIFACT_MODEL_BASE_URL', 'WOOBE_ARTIFACT_MODEL_API_KEY')


@pytest.fixture(autouse=True)
def isolated_selection(monkeypatch):
    for name in (*NAMES, 'WOOBE_ARTIFACT_RUN_LIVE_MODEL'):
        monkeypatch.delenv(name, raising=False)


def test_no_provider_connection_is_required_without_explicit_live_opt_in(monkeypatch):
    monkeypatch.setenv('WOOBE_ARTIFACT_OPENAI_API_KEY', 'legacy-private-canary')
    assert live_model_settings() is None


def test_openai_specific_binding_never_selects_a_provider_or_fills_generic_configuration(monkeypatch):
    monkeypatch.setenv('WOOBE_ARTIFACT_RUN_LIVE_MODEL', '1')
    monkeypatch.setenv('WOOBE_ARTIFACT_OPENAI_API_KEY', 'legacy-private-canary')
    with pytest.raises(ValueError) as error:
        live_model_settings()
    assert 'legacy-private-canary' not in str(error.value)


@pytest.mark.parametrize('provider', ['deepseek', 'openai_compatible', 'anthropic'])
def test_selected_provider_and_endpoint_are_preserved_without_openai_fallback(monkeypatch, provider):
    monkeypatch.setenv('WOOBE_ARTIFACT_RUN_LIVE_MODEL', '1')
    values = (provider, 'selected-model', 'https://chosen-provider.example/v1', 'selected-private-canary')
    for name, value in zip(NAMES, values, strict=True):
        monkeypatch.setenv(name, value)
    selected = live_model_settings()
    assert (selected.provider, selected.model, selected.destination, selected.credential) == values
    assert 'selected-private-canary' not in repr(selected)
