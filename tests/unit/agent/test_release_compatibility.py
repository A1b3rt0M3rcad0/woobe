import json

from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_versioning import ReleaseChangeKind


def release(response_format=None, output_schema=None):
    return AgentRelease(
        version="v0.0.20260620.00",
        response_format=response_format,
        output_schema=output_schema,
    )


def object_schema(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def test_none_previous_is_regular_change():
    assert classify_release_change(None, release()) == ReleaseChangeKind.CHANGE


def test_text_to_json_is_compatibility_break():
    previous = release(response_format={"type": "text"})
    candidate = release(response_format={"type": "json"})
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_strict_mode_change_is_compatibility_break():
    previous = release(response_format={"type": "json", "strict": False})
    candidate = release(response_format={"type": "json", "strict": True})
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_removed_output_field_is_compatibility_break():
    previous = release(output_schema=object_schema({"name": {"type": "string"}}))
    candidate = release(output_schema=object_schema({}))
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_output_parser_key_rename_confidence_to_message_is_compatibility_break():
    previous = release(output_schema=object_schema({"confidence": {"type": "number"}}))
    candidate = release(output_schema=object_schema({"message": {"type": "string"}}))
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_output_field_type_change_is_compatibility_break():
    previous = release(output_schema=object_schema({"score": {"type": "number"}}))
    candidate = release(output_schema=object_schema({"score": {"type": "string"}}))
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_response_format_schema_type_change_is_compatibility_break():
    previous = release(response_format={"type": "json", "schema": object_schema({"score": {"type": "number"}})})
    candidate = release(response_format={"type": "json", "schema": object_schema({"score": {"type": "string"}})})
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_response_format_schema_string_key_rename_is_compatibility_break():
    previous_schema = object_schema({"confidence": {"type": "number"}})
    candidate_schema = object_schema({"message": {"type": "string"}})
    previous = release(response_format={"type": "json", "schema": json.dumps(previous_schema)})
    candidate = release(response_format={"type": "json", "schema": json.dumps(candidate_schema)})
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_json_schema_wrapper_key_rename_is_compatibility_break():
    previous = release(response_format={"type": "json_schema", "json_schema": {"schema": object_schema({"confidence": {"type": "number"}})}})
    candidate = release(response_format={"type": "json_schema", "json_schema": {"schema": object_schema({"message": {"type": "string"}})}})
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_added_optional_output_field_is_feature():
    previous = release(output_schema=object_schema({"name": {"type": "string"}}))
    candidate = release(output_schema=object_schema({
        "name": {"type": "string"},
        "score": {"type": "number"},
    }))
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.FEATURE


def test_same_output_contract_is_change():
    schema = object_schema({"name": {"type": "string"}})
    previous = release(response_format={"type": "json"}, output_schema=schema)
    candidate = release(response_format={"type": "json"}, output_schema=schema)
    candidate.system_prompt = "new prompt"
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.CHANGE
