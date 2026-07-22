from __future__ import annotations

from modules.evaluation.application.tool_reference_repair import (
    grouped_unknown_tools,
    repair_generated_tool_references,
)


def _payload(tool_name: str) -> dict:
    return {
        "cases": [
            {
                "name": "Clarify missing input",
                "message": "Calculate the total.",
                "expected_outcome": {
                    "type": "success",
                    "required_behavior": [],
                    "forbidden_behavior": [],
                },
                "expected_contract": {
                    "semantic_criteria": ["The response must be actionable."],
                    "tools": {"required": [tool_name], "forbidden": []},
                    "output_contract": {"required": True},
                },
            }
        ]
    }


def test_ask_question_is_converted_to_observable_behavior() -> None:
    repaired, warnings, errors = repair_generated_tool_references(
        _payload("ask_question"),
        allowed_names=[],
    )

    case = repaired["cases"][0]
    assert case["expected_contract"]["tools"]["required"] == []
    assert case["expected_outcome"]["required_behavior"] == [
        "Ask the user a clarifying question when required information is missing."
    ]
    assert errors == []
    assert warnings[0]["code"] == "converted_behavioral_tool_reference"


def test_exact_snapshot_tool_is_preserved() -> None:
    repaired, warnings, errors = repair_generated_tool_references(
        _payload("calculate_cost"),
        allowed_names=["calculate_cost"],
    )

    assert repaired["cases"][0]["expected_contract"]["tools"]["required"] == [
        "calculate_cost"
    ]
    assert warnings == []
    assert errors == []


def test_unknown_concrete_tool_remains_blocked() -> None:
    repaired, warnings, errors = repair_generated_tool_references(
        _payload("delete_invoice"),
        allowed_names=["calculate_cost"],
    )

    assert repaired["cases"][0]["expected_contract"]["tools"]["required"] == []
    assert warnings == []
    assert errors[0]["code"] == "unknown_tool"
    assert errors[0]["tool_name"] == "delete_invoice"


def test_unknown_tools_are_grouped_for_user_feedback() -> None:
    grouped = grouped_unknown_tools(
        [
            {
                "path": "cases[0].expected_contract.tools.required",
                "code": "unknown_tool",
                "tool_name": "missing_tool",
                "message": "missing",
            },
            {
                "path": "cases[3].expected_contract.tools.forbidden",
                "code": "unknown_tool",
                "tool_name": "missing_tool",
                "message": "missing",
            },
        ]
    )

    assert grouped == [
        {
            "tool_name": "missing_tool",
            "reference_count": 2,
            "paths": [
                "cases[0].expected_contract.tools.required",
                "cases[3].expected_contract.tools.forbidden",
            ],
            "message": (
                "Tool 'missing_tool' is referenced by 2 Test Case(s) but is "
                "not present in the selected snapshot."
            ),
        }
    ]
