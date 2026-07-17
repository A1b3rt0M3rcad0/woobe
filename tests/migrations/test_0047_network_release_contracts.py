from pathlib import Path


def test_network_release_contract_migration_is_linear_after_0046() -> None:
    source = Path(
        "migrations/versions/0047_network_release_contracts.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0047"' in source
    assert 'down_revision: str | None = "0046"' in source
    assert '"public_output_contract"' in source
    assert '"agent_release_manifest"' in source
    assert '"release_fingerprint"' in source
    assert '"parsed_output"' in source
    assert '"network_production_activations"' in source
    assert '"ck_network_versions_change_kind"' in source
