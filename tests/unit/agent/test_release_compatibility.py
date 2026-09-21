import json

from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_compatibility import (
    classify_release_change,
    normalize_output_schema,
    output_schemas_equivalent,
)
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


def test_abbreviated_output_contract_key_rename_message_to_messagev2_is_break():
    previous = release(output_schema={"message": "string"})
    candidate = release(output_schema={"messagev2": "string"})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_example_output_contract_key_rename_message_to_messagev2_is_break():
    previous = release(output_schema={"message": "hello"})
    candidate = release(output_schema={"messagev2": "hello"})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_abbreviated_response_format_schema_key_rename_is_break():
    previous = release(response_format={"type": "json", "schema": {"message": {"type": "string"}}})
    candidate = release(response_format={"type": "json", "schema": {"messagev2": {"type": "string"}}})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_nested_abbreviated_contract_key_rename_is_break():
    previous = release(output_schema={"data": {"message": "string"}})
    candidate = release(output_schema={"data": {"messagev2": "string"}})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_added_optional_output_field_is_feature():
    previous = release(output_schema=object_schema({"name": {"type": "string"}}))
    candidate = release(output_schema=object_schema({
        "name": {"type": "string"},
        "score": {"type": "number"},
    }))
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.FEATURE


def test_abbreviated_contract_added_field_is_feature():
    previous = release(output_schema={"message": "string"})
    candidate = release(output_schema={"message": "string", "confidence": "number"})

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.FEATURE


def test_same_output_contract_is_change():
    schema = object_schema({"name": {"type": "string"}})
    previous = release(response_format={"type": "json"}, output_schema=schema)
    candidate = release(response_format={"type": "json"}, output_schema=schema)
    candidate.system_prompt = "new prompt"
    assert classify_release_change(previous, candidate) == ReleaseChangeKind.CHANGE


def test_public_output_schema_normalization_preserves_compact_required_fields():
    assert normalize_output_schema({
        "message": "string",
        "confidence": "float",
    }) == {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["message", "confidence"],
    }


def test_sdk_json_schema_matches_equivalent_compact_output_contract():
    server_contract = {
        "message": "string",
        "confidence": "float",
    }
    sdk_output_context = {
        "title": "SupportOutput",
        "type": "object",
        "properties": {
            "message": {"title": "Message", "type": "string"},
            "confidence": {"title": "Confidence", "type": "number"},
        },
        "required": ["message", "confidence"],
    }

    assert output_schemas_equivalent(server_contract, sdk_output_context) is True


def test_sdk_output_context_detects_required_field_type_mismatch():
    server_contract = {
        "message": "string",
        "confidence": "float",
    }
    sdk_output_context = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "confidence": {"type": "string"},
        },
        "required": ["message", "confidence"],
    }

    assert output_schemas_equivalent(server_contract, sdk_output_context) is False
