from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_versioning import ReleaseChangeKind


def release(schema):
    return AgentRelease(version="v0.0.20260620.00", output_schema=schema)


def test_simple_output_contract_key_rename_is_compatibility_change():
    previous = release({"message": "string"})
    candidate = release({"messagev2": "string"})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_simple_output_contract_type_change_is_compatibility_change():
    previous = release({"message": "string"})
    candidate = release({"message": "number"})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_simple_output_contract_added_field_is_feature_change():
    previous = release({"message": "string"})
    candidate = release({"message": "string", "confidence": "number"})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.FEATURE
