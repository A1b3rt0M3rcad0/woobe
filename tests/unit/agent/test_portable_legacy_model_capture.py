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
