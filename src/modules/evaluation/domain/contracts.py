from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.infra.errors import ValidationError

CASE_TYPES = {"success", "refusal", "handled_error", "expected_failure"}
FAILURE_ORIGINS = {"target", "provider", "tool", "contract", "policy", "platform", "cancelled"}
FAILURE_STAGES = {
    "snapshot",
    "runtime",
    "provider_call",
    "tool_execution",
    "output_validation",
    "judge",
    "persistence",
}
PLATFORM_FAILURE_CODES = {
    "evaluation_reference_missing",
    "worker_unavailable",
    "snapshot_corrupted",
    "snapshot_unavailable",
    "persistence_error",
    "lease_lost",
    "internal_error",
}


@dataclass(frozen=True)
class OutcomeAssessment:
    passed: bool | None
    status: str
    score: float | None
    reason: str
    evidence: dict[str, Any]
    blocking: bool = True


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalized_strings(value: Any) -> list[str]:
    return [item.lower() for item in _strings(value)]


def normalize_expected_outcome(case_type: str, raw: Any) -> dict[str, Any]:
    normalized_type = str(case_type or "success").strip().lower()
    if normalized_type not in CASE_TYPES:
        raise ValidationError(f"Unsupported Evaluation case_type: {normalized_type}")
    value = raw if isinstance(raw, dict) else {}
    outcome_type = str(value.get("type") or normalized_type).strip().lower()
    if outcome_type != normalized_type:
        raise ValidationError("expected_outcome.type must match case_type")

    origins = _normalized_strings(value.get("allowed_failure_origins"))
    stages = _normalized_strings(value.get("allowed_failure_stages"))
    codes = _normalized_strings(value.get("allowed_failure_codes"))
    invalid_origins = sorted(set(origins) - FAILURE_ORIGINS)
    invalid_stages = sorted(set(stages) - FAILURE_STAGES)
    if invalid_origins:
        raise ValidationError("Invalid expected failure origins: " + ", ".join(invalid_origins))
    if invalid_stages:
        raise ValidationError("Invalid expected failure stages: " + ", ".join(invalid_stages))
    if "platform" in origins or any(code in PLATFORM_FAILURE_CODES for code in codes):
        raise ValidationError("Platform failures cannot be accepted as an expected outcome")
    if normalized_type == "expected_failure" and not (origins or stages or codes):
        raise ValidationError(
            "expected_failure requires at least one allowed failure origin, stage or code"
        )

    required_behavior = _strings(value.get("required_behavior"))
    forbidden_behavior = _strings(value.get("forbidden_behavior"))
    return {
        "type": normalized_type,
        "allowed_failure_origins": origins,
        "allowed_failure_stages": stages,
        "allowed_failure_codes": codes,
        "required_behavior": required_behavior,
        "forbidden_behavior": forbidden_behavior,
    }


def normalize_test_case(raw: dict[str, Any], *, position: int) -> dict[str, Any]:
    name = str(raw.get("name") or f"Case {position}").strip()
    message = raw.get("message")
    input_payload = raw.get("input_payload")
    if not isinstance(input_payload, dict):
        input_payload = {"message": message} if isinstance(message, str) else {}
    resolved_message = (
        input_payload.get("message")
        or input_payload.get("input")
        or input_payload.get("prompt")
    )
    if not isinstance(resolved_message, str) or not resolved_message.strip():
        raise ValidationError(f"Test Case {position} requires a message input")
    input_payload = dict(input_payload)
    input_payload["message"] = resolved_message.strip()
    input_payload.pop("input", None)
    input_payload.pop("prompt", None)

    case_type = str(raw.get("case_type") or "success").strip().lower()
    expected_contract = raw.get("expected_contract")
    expected_contract = dict(expected_contract) if isinstance(expected_contract, dict) else {}
    expected_outcome = normalize_expected_outcome(
        case_type,
        raw.get("expected_outcome") or expected_contract.get("expected_outcome"),
    )
    expected_contract["expected_outcome"] = expected_outcome

    semantic = expected_contract.get("semantic_criteria")
    if not isinstance(semantic, list):
        expected_text = raw.get("expected") or raw.get("expected_result")
        semantic = [str(expected_text).strip()] if expected_text else []
    expected_contract["semantic_criteria"] = [
        str(item).strip() for item in semantic if str(item).strip()
    ]
    if (
        case_type != "expected_failure"
        and not expected_contract["semantic_criteria"]
        and not expected_outcome["required_behavior"]
        and not expected_outcome["forbidden_behavior"]
    ):
        raise ValidationError(
            f"Test Case {position} requires observable grading criteria or behavior"
        )

    output_contract = expected_contract.get("output_contract")
    if not isinstance(output_contract, dict):
        output_contract = {}
    if "required" not in output_contract:
        output_contract["required"] = case_type != "expected_failure"
    expected_contract["output_contract"] = output_contract

    severity = str(raw.get("severity") or "normal").strip().lower()
    if severity not in {"low", "normal", "high", "critical"}:
        raise ValidationError(f"Test Case {position} has invalid severity")
    weight = float(raw.get("weight") or 1.0)
    if weight <= 0 or weight > 100:
        raise ValidationError(f"Test Case {position} weight must be between 0 and 100")
    frequency = raw.get("production_frequency")
    if frequency is not None:
        frequency = float(frequency)
        if frequency < 0 or frequency > 1:
            raise ValidationError(
                f"Test Case {position} production_frequency must be between 0 and 1"
            )

    context = raw.get("initial_context")
    return {
        "name": name,
        "case_type": case_type,
        "input_payload": input_payload,
        "initial_context": context if isinstance(context, dict) else None,
        "expected_contract": expected_contract,
        "severity": severity,
        "weight": weight,
        "blocking": bool(raw.get("blocking", False)),
        "tags": _strings(raw.get("tags"))[:50],
        "production_frequency": frequency,
    }


def validate_suite_draft(payload: dict[str, Any]) -> dict[str, Any]:
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValidationError("Evaluator Suite requires at least one Test Case")
    if len(raw_cases) > 500:
        raise ValidationError("Evaluator Suite supports at most 500 Test Cases")

    normalized: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    signatures: set[tuple[str, str]] = set()
    duplicate_positions: list[int] = []
    for index, raw in enumerate(raw_cases, start=1):
        if not isinstance(raw, dict):
            errors.append({"path": f"cases[{index - 1}]", "message": "Case must be an object"})
            continue
        try:
            item = normalize_test_case(raw, position=index)
            signature = (
                item["case_type"],
                str(item["input_payload"].get("message") or "").strip().lower(),
            )
            if signature in signatures:
                duplicate_positions.append(index)
            signatures.add(signature)
            normalized.append(item)
        except (ValidationError, TypeError, ValueError) as exc:
            errors.append({"path": f"cases[{index - 1}]", "message": str(exc)})

    coverage: dict[str, int] = {}
    for item in normalized:
        labels = item.get("tags") or [item["case_type"]]
        for label in labels:
            coverage[str(label)] = coverage.get(str(label), 0) + 1
    warnings: list[dict[str, Any]] = []
    if duplicate_positions:
        warnings.append(
            {
                "code": "duplicate_cases",
                "message": "Potential duplicate questions were detected",
                "positions": duplicate_positions,
            }
        )
    if normalized and not any(item["case_type"] != "success" for item in normalized):
        warnings.append(
            {
                "code": "no_negative_cases",
                "message": "The Suite has no refusal or error-handling cases",
            }
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "coverage": coverage,
        "case_count": len(normalized),
        "cases": normalized,
    }


def classify_runtime_failure(exc: Exception) -> dict[str, Any]:
    name = type(exc).__name__
    message = " ".join(str(exc).split())[:1000]
    lowered = f"{name} {message}".lower()
    origin = "platform"
    stage = "runtime"
    code = "internal_error"

    if "cancel" in lowered:
        origin, stage, code = "cancelled", "runtime", "evaluation_cancelled"
    elif any(token in lowered for token in ("database", "sqlalchemy", "sql ", "transaction", "commit")):
        origin, stage, code = "platform", "persistence", "persistence_error"
    elif "lease" in lowered:
        origin, stage, code = "platform", "runtime", "lease_lost"
    elif "worker" in lowered:
        origin, stage, code = "platform", "runtime", "worker_unavailable"
    elif any(token in lowered for token in ("snapshot", "reference missing", "not found: evaluation")):
        origin, stage, code = "platform", "snapshot", "snapshot_unavailable"
    elif "tool" in lowered:
        origin, stage = "tool", "tool_execution"
        if "timeout" in lowered or "timed out" in lowered:
            code = "tool_timeout"
        elif any(token in lowered for token in ("429", "rate limit", "ratelimit")):
            code = "tool_rate_limited"
        elif any(token in lowered for token in ("401", "403", "unauthorized", "forbidden")):
            code = "tool_unauthorized"
        elif any(token in lowered for token in ("404", "not found")):
            code = "tool_not_found"
        elif any(token in lowered for token in ("http", "status code", "connection")):
            code = "tool_http_error"
        else:
            code = "tool_execution_failed"
    elif any(
        token in lowered
        for token in (
            "provider",
            "model call",
            "llm",
            "openai",
            "anthropic",
            "gemini",
            "rate limit",
            "ratelimit",
            "429",
            "502",
            "503",
            "504",
            "timeout",
        )
    ):
        origin, stage = "provider", "provider_call"
        if "timeout" in lowered or "timed out" in lowered:
            code = "provider_timeout"
        elif any(token in lowered for token in ("429", "rate limit", "ratelimit")):
            code = "provider_rate_limited"
        elif any(token in lowered for token in ("502", "503", "504", "unavailable")):
            code = "provider_unavailable"
        elif any(token in lowered for token in ("401", "403", "unauthorized")):
            code = "provider_unauthorized"
        else:
            code = "provider_call_failed"
    elif any(token in lowered for token in ("schema", "parse", "contract", "validation")):
        origin, stage, code = "contract", "output_validation", "output_contract_violation"
    elif any(token in lowered for token in ("policy", "forbidden", "not allowed", "denied")):
        origin, stage, code = "policy", "runtime", "policy_denied"
    elif any(token in lowered for token in ("target", "agent execution", "network execution")):
        origin, stage, code = "target", "runtime", "target_execution_failed"

    return {
        "type": "failure",
        "failure_origin": origin,
        "failure_stage": stage,
        "failure_code": code,
        "failure_detail": message,
        "exception_type": name,
    }


def assess_expected_outcome(
    *,
    case_type: str,
    expected_outcome: dict[str, Any] | None,
    observed_outcome: dict[str, Any] | None,
    answer: str | None,
) -> OutcomeAssessment:
    expected = normalize_expected_outcome(case_type, expected_outcome)
    observed = observed_outcome or {"type": "success"}
    observed_type = str(observed.get("type") or "success").lower()
    origin = str(observed.get("failure_origin") or "").lower()
    stage = str(observed.get("failure_stage") or "").lower()
    code = str(observed.get("failure_code") or "").lower()
    evidence = {"expected": expected, "observed": observed}

    if origin == "platform" or code in PLATFORM_FAILURE_CODES:
        return OutcomeAssessment(
            passed=None,
            status="inconclusive",
            score=None,
            reason="A platform failure cannot satisfy an Evaluator Test Case.",
            evidence=evidence,
        )
    if origin == "cancelled":
        return OutcomeAssessment(
            passed=None,
            status="inconclusive",
            score=None,
            reason="A cancelled Evaluation does not produce a quality judgment.",
            evidence=evidence,
        )

    if case_type == "expected_failure":
        if observed_type != "failure":
            return OutcomeAssessment(False, "failed", 0.0, "The expected failure did not occur.", evidence)
        allowed_origins = set(expected["allowed_failure_origins"])
        allowed_stages = set(expected["allowed_failure_stages"])
        allowed_codes = set(expected["allowed_failure_codes"])
        matches = (
            (not allowed_origins or origin in allowed_origins)
            and (not allowed_stages or stage in allowed_stages)
            and (not allowed_codes or code in allowed_codes)
        )
        return OutcomeAssessment(
            matches,
            "passed" if matches else "failed",
            100.0 if matches else 0.0,
            "The observed failure matches the expected contract."
            if matches
            else "The observed failure does not match the expected origin, stage or code.",
            evidence,
        )

    if observed_type == "failure":
        return OutcomeAssessment(
            False,
            "failed",
            0.0,
            "The target failed before producing the expected controlled behavior.",
            evidence,
        )

    has_answer = isinstance(answer, str) and bool(answer.strip())
    if case_type in {"success", "refusal", "handled_error"} and not has_answer:
        return OutcomeAssessment(False, "failed", 0.0, "The target returned no public response.", evidence)
    return OutcomeAssessment(
        True,
        "passed",
        100.0,
        f"The target produced a {case_type} outcome eligible for semantic judgment.",
        evidence,
    )


__all__ = [
    "CASE_TYPES",
    "FAILURE_ORIGINS",
    "FAILURE_STAGES",
    "OutcomeAssessment",
    "assess_expected_outcome",
    "classify_runtime_failure",
    "normalize_expected_outcome",
    "normalize_test_case",
    "validate_suite_draft",
]
