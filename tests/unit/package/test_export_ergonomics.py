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
