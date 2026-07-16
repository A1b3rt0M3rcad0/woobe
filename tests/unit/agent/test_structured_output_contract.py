from __future__ import annotations

from modules.agent.application.use_cases.structured_output_contract import (
    format_contract_errors,
    normalize_contract_for_prompt,
    validate_output_against_contract,
)


def test_float_contract_accepts_numeric_output() -> None:
    schema = {"message": "string", "confidence": "float"}
    parsed_output = {"message": "ok", "confidence": 0.87}

    assert validate_output_against_contract(parsed_output, schema) == []


def test_number_contract_rejects_literal_type_name_output() -> None:
    schema = {"message": "string", "confidence": "number"}
    parsed_output = {"message": "ok", "confidence": "number"}

    errors = validate_output_against_contract(parsed_output, schema)

    assert len(errors) == 1
    assert errors[0].path == "$.confidence"
    assert errors[0].expected == "number"
    assert errors[0].received == "string"
    assert format_contract_errors(errors) == "$.confidence expected number, received string"


def test_contract_aliases_are_normalized_for_prompt() -> None:
    schema = {
        "message": "str",
        "confidence": "float",
        "flags": ["bool"],
        "metadata": {"type": "dict", "properties": {"score": {"type": "decimal"}}},
    }

    assert normalize_contract_for_prompt(schema) == {
        "message": "string",
        "confidence": "number",
        "flags": ["boolean"],
        "metadata": {"type": "object", "properties": {"score": {"type": "number"}}},
    }


def test_missing_required_shorthand_field_is_reported() -> None:
    schema = {"message": "string", "confidence": "float"}
    parsed_output = {"message": "ok"}

    errors = validate_output_against_contract(parsed_output, schema)

    assert len(errors) == 1
    assert errors[0].path == "$.confidence"
    assert errors[0].expected == "present"
    assert errors[0].received == "missing"
