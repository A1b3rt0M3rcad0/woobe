from modules.evaluation.domain.authoring_contract import (
    generation_failure_metadata,
    normalize_authoring_payload,
    suite_generation_json_schema,
)
from modules.evaluation.domain.contracts import validate_suite_draft


def _case() -> dict:
    return {
        "name": "Billing question",
        "case_type": "success",
        "message": "How do I update my billing address?",
        "expected_outcome": {
            "type": "success",
            "required_behavior": "Explain the supported process",
            "forbidden_behavior": "Do not invent customer data",
        },
        "expected_contract": {
            "semantic_criteria": "The response must address billing",
            "tools": {"required": "billing_lookup", "forbidden": []},
            "output_contract": {"required": True},
        },
        "severity": "normal",
        "weight": 1,
        "blocking": False,
        "tags": "billing",
        "production_frequency": 0.4,
    }


def test_normalizes_generated_string_fields_to_lists() -> None:
    payload, warnings = normalize_authoring_payload(
        {"schema_version": 1, "suite": {}, "coverage": {}, "cases": [_case()]}
    )

    case = payload["cases"][0]
    assert case["expected_outcome"]["required_behavior"] == [
        "Explain the supported process"
    ]
    assert case["expected_outcome"]["forbidden_behavior"] == [
        "Do not invent customer data"
    ]
    assert case["expected_contract"]["semantic_criteria"] == [
        "The response must address billing"
    ]
    assert case["expected_contract"]["tools"]["required"] == ["billing_lookup"]
    assert case["tags"] == ["billing"]
    assert any(item["code"] == "normalized_string_to_list" for item in warnings)
    assert validate_suite_draft(payload)["valid"] is True


def test_normalizes_expected_behavior_alias() -> None:
    case = _case()
    case.pop("expected_outcome")
    case["expected_behavior"] = "Ask for the missing customer identifier"
    case["expected_contract"]["semantic_criteria"] = []

    payload, warnings = normalize_authoring_payload(
        {"schema_version": 1, "suite": {}, "coverage": {}, "cases": [case]}
    )

    assert payload["cases"][0]["expected_outcome"]["required_behavior"] == [
        "Ask for the missing customer identifier"
    ]
    assert any(
        item["code"] == "normalized_expected_behavior_alias" for item in warnings
    )
    assert validate_suite_draft(payload)["valid"] is True


def test_contract_still_rejects_case_without_observable_criteria() -> None:
    case = _case()
    case["expected_outcome"]["required_behavior"] = []
    case["expected_outcome"]["forbidden_behavior"] = []
    case["expected_contract"]["semantic_criteria"] = []

    payload, _ = normalize_authoring_payload(
        {"schema_version": 1, "suite": {}, "coverage": {}, "cases": [case]}
    )
    validation = validate_suite_draft(payload)

    assert validation["valid"] is False
    assert "observable grading criteria" in validation["errors"][0]["message"]


def test_failure_metadata_distinguishes_contract_and_credentials() -> None:
    contract = generation_failure_metadata(
        None,
        {
            "errors": [
                {
                    "path": "cases[0]",
                    "message": "Observable criteria are required",
                }
            ]
        },
    )
    credential = generation_failure_metadata("401 unauthorized credential", None)

    assert contract == {
        "category": "invalid_case_contract",
        "retryable": True,
        "recommended_action": "repair_invalid_cases",
    }
    assert credential["category"] == "credential_error"
    assert credential["retryable"] is False


def test_generation_schema_requires_observable_contract_fields() -> None:
    schema = suite_generation_json_schema()
    case_schema = schema["properties"]["cases"]["items"]
    expected = case_schema["properties"]["expected_outcome"]
    contract = case_schema["properties"]["expected_contract"]

    assert "required_behavior" in expected["required"]
    assert "forbidden_behavior" in expected["required"]
    assert "semantic_criteria" in contract["required"]
