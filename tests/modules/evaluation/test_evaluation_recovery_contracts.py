from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from modules.evaluation.domain.authoring_contract import suite_generation_json_schema
from modules.evaluation.domain.contracts import validate_suite_draft
from modules.evaluation.infra.budgeted_judge import _reasoning_policy
from modules.evaluation.infra.judge import JudgeResult
from modules.evaluation.infra.resilient_judge import (
    _canonicalize_repair_payload,
    _extract_json_object,
    _repairable,
)


def _valid_case(name: str, message: str) -> dict:
    return {
        "name": name,
        "case_type": "success",
        "message": message,
        "expected_outcome": {
            "type": "success",
            "allowed_failure_origins": [],
            "allowed_failure_stages": [],
            "allowed_failure_codes": [],
            "required_behavior": ["Answer the question directly."],
            "forbidden_behavior": [],
        },
        "expected_contract": {
            "semantic_criteria": ["The response addresses the requested subject."],
            "tools": {"required": [], "forbidden": []},
            "output_contract": {"required": True},
        },
        "severity": "normal",
        "weight": 1,
        "blocking": False,
        "tags": [],
        "production_frequency": None,
    }


def _failed_result(error: str) -> JudgeResult:
    now = datetime.now(timezone.utc)
    return JudgeResult(
        provider_model_id=uuid4(),
        provider_credential_id=uuid4(),
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        judge_config_hash="config",
        rubric_hash="rubric",
        status="failed",
        input_tokens=100,
        output_tokens=100,
        cost_usd=0.01,
        cost_status="known",
        cost_reason=None,
        pricing_snapshot={},
        latency_ms=10,
        structured_result=None,
        error=error,
        started_at=now,
        completed_at=now,
    )


def test_generation_schema_requires_observable_semantic_criterion() -> None:
    schema = suite_generation_json_schema()
    semantic = (
        schema["properties"]["cases"]["items"]["properties"]
        ["expected_contract"]["properties"]["semantic_criteria"]
    )

    assert semantic["minItems"] == 1
    assert semantic["items"]["minLength"] == 1


def test_validation_preserves_original_case_positions() -> None:
    invalid = _valid_case("Invalid", "First")
    invalid["expected_contract"]["semantic_criteria"] = []
    invalid["expected_outcome"]["required_behavior"] = []
    valid = _valid_case("Valid", "Second")

    result = validate_suite_draft({"cases": [invalid, valid]})

    assert result["valid"] is False
    assert result["case_count"] == 1
    assert result["cases"][0] is None
    assert result["cases"][1]["name"] == "Valid"
    assert result["valid_cases"][0]["name"] == "Valid"


def test_repair_parser_extracts_json_from_provider_prose() -> None:
    parsed = _extract_json_object(
        "Provider preface\n```json\n"
        '{"status":"passed","score":91,"confidence":"high",'
        '"dimensions":{},"criteria":[],"failures":[],"summary":"ok"}'
        "\n```"
    )

    assert parsed["score"] == 91


def test_repair_payload_normalizes_common_verdict_aliases() -> None:
    normalized = _canonicalize_repair_payload(
        {"verdict": "pass", "overall_score": 88, "reason": "acceptable"}
    )

    assert normalized["status"] == "passed"
    assert normalized["score"] == 88
    assert normalized["confidence"] == "medium"
    assert normalized["summary"] == "acceptable"


def test_invalid_json_failure_is_repairable() -> None:
    assert _repairable(_failed_result("judge_failed: JSONDecodeError invalid JSON")) is True


def test_credential_failure_is_not_repairable() -> None:
    assert _repairable(_failed_result("judge_failed: 401 unauthorized credential")) is False


def test_reasoning_controls_are_opt_in_by_default() -> None:
    assert _reasoning_policy({}, {}) == "provider_default"
    assert _reasoning_policy({"supports_reasoning": True}, {}) == "provider_default"


def test_explicit_reasoning_policy_is_preserved() -> None:
    assert _reasoning_policy({}, {"reasoning_policy": "disabled"}) == "disabled"
