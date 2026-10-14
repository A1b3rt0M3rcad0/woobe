import json
from pathlib import Path
from copy import deepcopy
import pytest

from modules.package.application.asac_definition import portable_definition
from modules.package.infra.bundles import snapshot_directory


def test_closed_definition_matches_shared_go_fixture(tmp_path):
    root = Path(__file__).resolve().parents[3] / "specs/package/v1/fixtures"
    fixture = json.loads((root / "complete.json").read_text())
    for name, content in fixture["files"].items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    expected = json.loads((root / "asac-portable-definition.json").read_text())
    with snapshot_directory(tmp_path) as bundle:
        digest, components = portable_definition(bundle)
        assert digest == expected["definition_digest"]
        assert components == expected["components"]
        # Renaming a portable key and updating references must preserve meaning.
        bundle.graph.manifest["metadata"]["name"] = "Transport label"
        assert portable_definition(bundle)[0] == digest
        bundle.graph.components["support"]["spec"]["model"]["parameters"]["temperature"] = 0.5
        assert portable_definition(bundle)[0] != digest


def test_configuration_definition_matches_shared_go_fixture_and_captures_semantics(tmp_path):
    from modules.package.application.asac_definition import definition_scope, provider_definition_digests
    root = Path(__file__).resolve().parents[3] / "specs/package/v2/fixtures"
    fixture = json.loads((root / "asac-portable-definition.json").read_text())
    for name, content in fixture["files"].items():
        (tmp_path / name).write_text(content)
    with snapshot_directory(tmp_path) as bundle:
        digest, components = portable_definition(bundle)
        assert digest == fixture["definition_digest"]
        assert components == fixture["components"]
        assert definition_scope(bundle.graph.manifest) == fixture["definition_digest_scope"]
        assert provider_definition_digests(bundle.graph.manifest) == fixture["providers"]
        spec = bundle.graph.manifest["spec"]
        original = deepcopy(spec)
        # Array presentation and logical connection aliases are not semantics.
        spec["configuration"]["keys"].reverse()
        spec["connections"]["renamed"] = spec["connections"].pop("primary")
        spec["connections"]["renamed"]["name"] = "A different display name"
        bundle.graph.components["model"]["spec"]["credential"]["ref"] = "renamed"
        assert portable_definition(bundle)[0] == digest
        bundle.graph.components["model"]["spec"]["credential"]["ref"] = "primary"
        for field, value in (("authentication", {"type": "api_key", "fields": {"api_key": {"source": "project_environment", "key": "ANOTHER_KEY"}}}),
                             ("metadata", {"base_url": "https://another.example/v1"})):
            bundle.graph.manifest["spec"] = deepcopy(original)
            bundle.graph.manifest["spec"]["connections"]["primary"][field] = value
            assert portable_definition(bundle)[0] != digest
        bundle.graph.manifest["spec"] = deepcopy(original)
        bundle.graph.manifest["spec"]["configuration"]["keys"][0]["validation_rules"] = {"min_length": 8}
        assert portable_definition(bundle)[0] != digest


def test_unknown_definition_version_is_not_reinterpreted(tmp_path):
    from modules.package.application.asac_definition import definition_scope
    from modules.package.domain.errors import PackageError
    with pytest.raises(PackageError, match="Unsupported portable"):
        definition_scope({"schema_version": "3.0"})
