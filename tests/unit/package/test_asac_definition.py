import json
from pathlib import Path

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
