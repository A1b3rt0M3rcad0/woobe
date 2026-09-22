from shared.contracts.runtime_contracts import (
    compare_contract_schema,
    external_context_contract_schema,
    normalize_contract_schema,
)


def test_contract_presence_must_match_explicit_null() -> None:
    assert compare_contract_schema(None, None)["valid"] is True

    missing = compare_contract_schema({"message": "string"}, None)
    assert missing["valid"] is False
    assert missing["issues"][0]["code"] == "CONTRACT_PRESENCE_MISMATCH"


def test_annotations_are_ignored_but_real_title_field_is_preserved() -> None:
    expected = normalize_contract_schema(
        {
            "type": "object",
            "title": "Runtime output",
            "properties": {
                "title": {
                    "type": "string",
                    "title": "Title metadata",
                    "description": "Ignored annotation",
                },
                "message": {"type": "string"},
            },
            "required": ["message", "title"],
        }
    )
    received = normalize_contract_schema(
        {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["title", "message"],
        }
    )

    assert expected == received
    assert compare_contract_schema(expected, received)["valid"] is True
    assert "title" in expected["properties"]


def test_external_context_sdk_schema_preserves_scope_metadata() -> None:
    schema = external_context_contract_schema(
        {
            "age": {
                "schema": {"type": "integer"},
                "required": True,
                "scope": "session",
                "description": "Model-independent metadata",
                "model": {"expose": False},
            },
            "title": {
                "schema": {"type": "string"},
                "required": False,
                "model": {"expose": True},
            },
        }
    )

    assert schema == {
        "additionalProperties": False,
        "properties": {
            "age": {"type": "integer", "x-woobe-scope": "session"},
            "title": {"type": "string", "x-woobe-scope": "run"},
        },
        "required": ["age"],
        "type": "object",
    }


def test_nested_array_enum_and_additional_properties_are_structural() -> None:
    expected = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["a", "b"]},
                    },
                    "required": ["kind"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["items"],
        "additionalProperties": False,
    }

    changed_enum = {
        **expected,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["a", "c"]},
                    },
                    "required": ["kind"],
                    "additionalProperties": False,
                },
            },
        },
    }
    enum_result = compare_contract_schema(expected, changed_enum)
    assert enum_result["valid"] is False
    assert any(issue["code"] == "ENUM_MISMATCH" for issue in enum_result["issues"])

    changed_additional = {
        **expected,
        "additionalProperties": True,
    }
    additional_result = compare_contract_schema(expected, changed_additional)
    assert additional_result["valid"] is False
    assert any(
        issue["code"] == "ADDITIONAL_PROPERTIES_MISMATCH"
        for issue in additional_result["issues"]
    )


def test_required_and_extra_fields_are_reported_separately() -> None:
    expected = {
        "type": "object",
        "properties": {
            "age": {"type": "integer"},
            "title": {"type": "string"},
        },
        "required": ["age", "title"],
        "additionalProperties": False,
    }
    received = {
        "type": "object",
        "properties": {
            "age": {"type": "integer"},
            "extra": {"type": "string"},
        },
        "required": ["age"],
        "additionalProperties": False,
    }

    result = compare_contract_schema(expected, received)
    codes = {issue["code"] for issue in result["issues"]}

    assert result["valid"] is False
    assert "REQUIRED_FIELD_MISSING" in codes
    assert "FIELD_MISSING" in codes
    assert "FIELD_EXTRA" in codes
