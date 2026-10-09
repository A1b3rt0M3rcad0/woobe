import yaml
import pytest
from pydantic import ValidationError

from modules.package.application.requests import ExportPackageRequest
from modules.package.application.export_projection import portable_yaml

TARGET = "00000000-0000-4000-8000-000000000001"


def test_export_defaults_and_release_selector():
    request = ExportPackageRequest(kind="Agent", target_id=TARGET)
    assert request.source == "draft"
    assert request.name is None and request.version is None
    release = ExportPackageRequest(
        kind="Network", target_id=TARGET, source="release", release_version="1.2.0"
    )
    assert release.release_version == "1.2.0"
    exact = ExportPackageRequest(kind="Agent", target_id=TARGET, snapshot_id=TARGET)
    assert exact.source is None
    for source in ("draft", "staging", "production"):
        with pytest.raises(ValidationError):
            ExportPackageRequest(
                kind="Agent", target_id=TARGET, source=source, release_version="1.2.0"
            )
    with pytest.raises(ValidationError):
        ExportPackageRequest(
            kind="Agent", target_id=TARGET, source="draft", snapshot_id=TARGET
        )


def test_yaml_preserves_strings_multiline_numbers_and_types():
    value = {
        "schema_version": "1.0",
        "date": "2026-10-07",
        "yes": "yes",
        "false": "false",
        "code": "001",
        "prompt": "First line\nSecond line\n",
        "enabled": False,
        "limit": 2,
        "nested": {"name": "Suporte & pedidos"},
    }
    serialized = portable_yaml(value).decode()
    assert yaml.safe_load(serialized) == value
    assert "prompt: |" in serialized
    assert "\n  First line\n  Second line\n" in serialized
    assert not serialized.startswith("{")


def test_yaml_shared_values_do_not_emit_forbidden_anchors():
    shared = {"ref": "model-primary"}
    value = {"primary": shared, "fallback": shared}
    serialized = portable_yaml(value).decode()
    assert yaml.safe_load(serialized) == value
    assert "&id" not in serialized and "*id" not in serialized


@pytest.mark.parametrize("text", [
    "First\nSecond", "First\nSecond\n", "\n", "\n\n", "  \n",
    "First\r\nSecond\r\n", "First\rSecond", "First\u0085Second\n",
    "First\u2028Second\n", "First\u2029Second\n", "\x00",
])
def test_yaml_preserves_instruction_line_separators_exactly(text):
    from modules.package.domain.parsing import decode_document

    value = {"instructions": text}
    serialized = portable_yaml(value)
    assert yaml.safe_load(serialized) == value
    assert decode_document(serialized, "agent.yaml") == value


@pytest.mark.parametrize("specification,credentials,message", [
    (None, {"credential": {"provider": "custom"}}, "ModelSpec"),
    ({"model_id": "fake"}, {}, "credential intent"),
    ({"model_id": "fake"}, {"credential": {"provider": "openai"}}, "provider differs"),
])
def test_incomplete_export_locates_the_agent_model_without_protected_values(specification, credentials, message):
    from modules.package.application.export_projection import ExportProjection
    from modules.package.domain.errors import PackageError
    projection = ExportProjection(knowledge_mode="binding", environment_kinds={})
    captured = {"definition": {"runtime_config": {}, "provider": "custom", "model": "fake", "provider_credential_id": "credential", "model_spec_snapshot": specification}, "credentials": credentials}
    with pytest.raises(PackageError, match=message) as caught:
        projection.agent(captured, "agent-1")
    diagnostic = caught.value.as_dict()
    assert diagnostic["code"] == "PACKAGE_EXPORT_INCOMPLETE"
    assert diagnostic["file"] == "agent-1.yaml"
    assert diagnostic["path"] == "/spec/model/primary"


@pytest.mark.parametrize('frozen',[False,True])
def test_canonical_root_identity_is_private_capture_evidence_not_portable_content(frozen):
    from modules.package.application.export_projection import ExportProjection
    uid='00000000-0000-4000-8000-000000000005'
    captured={'source':{'agent_id':TARGET,'kind':'draft','resource_uid':uid},
        'definition':{'name':'Support','provider':'custom','model':'fake','provider_credential_id':'credential',
                      'model_spec_snapshot':{'model_id':'fake'},'runtime_config':{},'system_prompt':'Help',
                      'session_mode':'stateless'},
        'credentials':{'credential':{'provider':'custom','metadata':{}}},
        'tools':[],'skills':[],'artifacts':{},'knowledge':None,'frozen':frozen}
    projection=ExportProjection(knowledge_mode='binding',environment_kinds={},development=True)
    projection.agent(captured,'agent-1')
    assert projection.native_bindings['agent-1'].get('resource_uid')==(None if frozen else uid)
    assert uid not in repr(projection.documents) and uid not in repr(projection.files)
