import pytest
from shared.contracts.errors import ValidationError
from types import SimpleNamespace
from uuid import uuid4

from modules.agent.application.portable_export_compiler import (
    PortableAgentExportCompiler,
)
from modules.agent.domain.model_spec import ModelSpec, model_spec_hash


def test_legacy_native_model_is_captured_without_rewriting_persistence():
    model = SimpleNamespace(
        id=uuid4(),
        name="Legacy",
        model="legacy-language",
        provider_credential_id=uuid4(),
        meta={"context_window": 4096},
        spec=None,
        spec_hash=None,
    )
    captured = PortableAgentExportCompiler.capture_model(model, provider="custom")
    assert captured.spec["provider"] == "custom"
    assert captured.spec_hash == model_spec_hash(ModelSpec.from_dict(captured.spec))
    assert model.spec is None and model.spec_hash is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"base_url": "https://user:private-provider-value@example.test/v1"},
        {"base_url": "https://example.test/v1?api_key=private-provider-value"},
        {"api_key": "private-provider-value"},
    ],
)
def test_legacy_model_authentication_cannot_become_a_portable_snapshot(metadata):
    model = SimpleNamespace(
        id=uuid4(),
        name="Legacy",
        model="legacy-language",
        provider_credential_id=uuid4(),
        meta=metadata,
        spec=None,
        spec_hash=None,
    )
    with pytest.raises(ValidationError) as error:
        PortableAgentExportCompiler.capture_model(model, provider="custom")
    assert "private-provider-value" not in str(error.value)
    assert model.spec is None
