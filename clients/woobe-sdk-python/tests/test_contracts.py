from __future__ import annotations

import pytest
from pydantic import BaseModel

from woobe.contracts import (
    contract_schema,
    external_context_contract_schema,
    output_context_schema,
)


class Detail(BaseModel):
    flags: list[bool]


class SupportOutput(BaseModel):
    message: str
    detail: Detail


def test_contract_schema_inlines_nested_pydantic_refs() -> None:
    schema = contract_schema(SupportOutput)

    assert schema is not None
    assert "$defs" not in schema
    assert schema["properties"]["detail"] == {
        "properties": {
            "flags": {
                "items": {"type": "boolean"},
                "title": "Flags",
                "type": "array",
            }
        },
        "required": ["flags"],
        "title": "Detail",
        "type": "object",
    }


def test_contract_schema_accepts_model_instance() -> None:
    schema = contract_schema(
        SupportOutput(
            message="ok",
            detail=Detail(flags=[True]),
        )
    )

    assert schema is not None
    assert schema["properties"]["message"]["type"] == "string"


def test_contract_schema_inlines_explicit_json_schema_refs() -> None:
    raw = {
        "$defs": {
            "Detail": {
                "type": "object",
                "properties": {"flag": {"type": "boolean"}},
                "required": ["flag"],
            }
        },
        "type": "object",
        "properties": {"detail": {"$ref": "#/$defs/Detail"}},
        "required": ["detail"],
    }

    assert contract_schema(raw) == {
        "type": "object",
        "properties": {
            "detail": {
                "type": "object",
                "properties": {"flag": {"type": "boolean"}},
                "required": ["flag"],
            }
        },
        "required": ["detail"],
    }


def test_external_context_uses_same_schema_conversion() -> None:
    schema = external_context_contract_schema(SupportOutput)

    assert schema is not None
    assert "$defs" not in schema
    assert schema["properties"]["message"]["type"] == "string"
    assert schema["additionalProperties"] is False


def test_output_context_schema_remains_backward_compatible() -> None:
    raw = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    assert output_context_schema(raw) == raw


def test_contract_schema_rejects_unsupported_values() -> None:
    with pytest.raises(TypeError, match="contract"):
        contract_schema("message: str")  # type: ignore[arg-type]
