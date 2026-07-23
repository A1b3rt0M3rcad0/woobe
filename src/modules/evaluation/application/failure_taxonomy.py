from __future__ import annotations

from typing import Any


def _text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


def canonical_judge_failure_code(
    *,
    failure_code: str | None,
    failure_detail: str | None,
    judge_status: str | None = None,
    judge_error: str | None = None,
) -> str | None:
    combined = _text(failure_code, failure_detail, judge_error)
    code = str(failure_code or "")
    judge_failed = (
        code.startswith("judge_")
        or judge_status == "failed"
        or "judge" in combined
        or "evaluator model" in combined
        or "lengthfinishreasonerror" in combined
        or "api status error" in combined
    )
    if not judge_failed:
        return None
    if any(
        value in combined
        for value in (
            "error code: 402",
            "status code: 402",
            "payment required",
            "requires more credits",
            "can only afford",
            "insufficient balance",
            "insufficient credits",
            "insufficient_quota",
            "spending limit",
            "credit limit",
            "judge_insufficient_balance",
            "judge_insufficient_credits",
        )
    ):
        return "judge_insufficient_credits"
    if any(
        value in combined
        for value in (
            "model not found",
            "no endpoints found",
            "model unavailable",
            "unknown model",
            "judge_model_unavailable",
        )
    ):
        return "judge_model_unavailable"
    if any(
        value in combined
        for value in (
            "context length",
            "context window",
            "maximum context",
            "too many input tokens",
            "prompt is too long",
        )
    ):
        return "judge_context_limit"
    if any(
        value in combined
        for value in (
            "unsupported parameter",
            "unknown parameter",
            "unrecognized parameter",
            "extra inputs are not permitted",
        )
    ):
        return "judge_unsupported_parameter"
    if any(
        value in combined
        for value in (
            "invalid json",
            "json decode",
            "structured response",
            "judge score must be numeric",
            "float() argument must be a string or a real number, not 'nonetype'",
        )
    ):
        return "judge_invalid_json"
    if any(
        value in combined
        for value in (
            "lengthfinishreasonerror",
            "length limit was reached",
            "finish_reason=length",
            "finish reason 'length'",
            "finish reason: length",
            "maximum output length",
            "max_completion_tokens",
            "completion length",
            "output token",
        )
    ):
        return "judge_output_length_limit"
    if any(value in combined for value in ("rate limit", "rate_limit", "429")):
        return "judge_rate_limited"
    if any(value in combined for value in ("timeout", "timed out")):
        return "judge_timeout"
    if any(
        value in combined
        for value in (
            "credential",
            "unauthorized",
            "error code: 401",
            "status code: 401",
            "error code: 403",
            "status code: 403",
            "forbidden",
        )
    ):
        return "judge_credential_invalid"
    if any(
        value in combined
        for value in (
            "error code: 500",
            "error code: 502",
            "error code: 503",
            "error code: 504",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
        )
    ):
        return "judge_provider_5xx"
    if any(value in combined for value in ("safety blocked", "content filtered", "moderation blocked")):
        return "judge_safety_blocked"
    if code.startswith("judge_"):
        return code
    return "judge_unknown_failure"


def judge_failure_policy(code: str | None) -> dict[str, Any]:
    policies: dict[str, dict[str, Any]] = {
        "judge_insufficient_credits": {
            "retryable": False,
            "repairable": False,
            "scope": "run",
            "circuit_breaker": True,
            "recoverability": "user_action_required",
            "recommended_action": "Add provider credits, reduce the Judge output budget or create a Suite Version with another Judge Model.",
        },
        "judge_credential_invalid": {
            "retryable": False,
            "repairable": False,
            "scope": "run",
            "circuit_breaker": True,
            "recoverability": "user_action_required",
            "recommended_action": "Activate a valid Project Credential for the Judge Model.",
        },
        "judge_model_unavailable": {
            "retryable": False,
            "repairable": False,
            "scope": "run",
            "circuit_breaker": True,
            "recoverability": "user_action_required",
            "recommended_action": "Create a new Suite Version with an active Judge Model.",
        },
        "judge_context_limit": {
            "retryable": False,
            "repairable": False,
            "scope": "trial",
            "circuit_breaker": False,
            "recoverability": "configuration_required",
            "recommended_action": "Reduce the Judge input budget or select a model with a larger context window.",
        },
        "judge_unsupported_parameter": {
            "retryable": False,
            "repairable": False,
            "scope": "model",
            "circuit_breaker": True,
            "recoverability": "configuration_required",
            "recommended_action": "Use the provider-default response strategy or select a compatible Judge Model.",
        },
        "judge_invalid_json": {
            "retryable": True,
            "repairable": True,
            "scope": "trial",
            "circuit_breaker": False,
            "recoverability": "retryable",
            "recommended_action": "Retry the affected Judgment with the compact structured-output repair.",
        },
        "judge_output_length_limit": {
            "retryable": True,
            "repairable": True,
            "scope": "trial",
            "circuit_breaker": False,
            "recoverability": "retryable",
            "recommended_action": "Retry within the immutable Suite output ceiling; do not raise the budget above the configured limit.",
        },
        "judge_rate_limited": {
            "retryable": True,
            "repairable": False,
            "scope": "credential",
            "circuit_breaker": False,
            "recoverability": "retryable",
            "recommended_action": "Resume after the provider rate limit clears.",
        },
        "judge_timeout": {
            "retryable": True,
            "repairable": False,
            "scope": "trial",
            "circuit_breaker": False,
            "recoverability": "retryable",
            "recommended_action": "Retry only the affected Judgments.",
        },
        "judge_provider_5xx": {
            "retryable": True,
            "repairable": False,
            "scope": "provider",
            "circuit_breaker": False,
            "recoverability": "retryable",
            "recommended_action": "Retry after the provider recovers.",
        },
        "judge_safety_blocked": {
            "retryable": False,
            "repairable": False,
            "scope": "trial",
            "circuit_breaker": False,
            "recoverability": "review_required",
            "recommended_action": "Review the Test Case and provider safety policy.",
        },
    }
    return policies.get(
        str(code or ""),
        {
            "retryable": False,
            "repairable": False,
            "scope": "trial",
            "circuit_breaker": False,
            "recoverability": "review_required",
            "recommended_action": "Review the persisted Judge diagnostics before retrying.",
        },
    )


def classify_evaluation_failure(
    *,
    trial_status: str | None,
    failure_code: str | None,
    failure_detail: str | None,
    judge_status: str | None = None,
    judge_error: str | None = None,
    runtime_completed: bool = False,
) -> dict[str, Any] | None:
    """Return one exclusive, user-facing failure classification."""

    combined = _text(failure_code, failure_detail, judge_error)
    code = str(failure_code or "")
    resolved = canonical_judge_failure_code(
        failure_code=failure_code,
        failure_detail=failure_detail,
        judge_status=judge_status,
        judge_error=judge_error,
    )
    if resolved is not None:
        policy = judge_failure_policy(resolved)
        return {
            "stage": "judge",
            "kind": "judge",
            "code": resolved,
            **policy,
            "summary": "The target output was preserved, but the Judge did not produce usable evidence.",
        }

    if not runtime_completed and trial_status in {"failed", "blocked", "cancelled"}:
        if any(value in combined for value in ("tool", "mcp", "http")):
            stage = "tool"
            kind = "execution"
        elif any(value in combined for value in ("knowledge", "rag", "vector", "retrieval")):
            stage = "knowledge"
            kind = "execution"
        else:
            stage = "target_runtime"
            kind = "execution"
        return {
            "stage": stage,
            "kind": kind,
            "code": code or "target_runtime_failed",
            "recoverability": "review_required",
            "recommended_action": "Inspect the target Trace and runtime error before rerunning the Evaluation.",
            "summary": "The selected snapshot did not complete a normal target execution.",
        }

    if trial_status == "inconclusive":
        return {
            "stage": "evidence",
            "kind": "inconclusive",
            "code": code or "evidence_inconclusive",
            "recoverability": "review_required",
            "recommended_action": "Review deterministic checks and Judge evidence.",
            "summary": "The available evidence could not produce a reliable score.",
        }

    return None


def summarize_failures(
    trials: list[dict[str, Any]],
    judge_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    calls = {str(item.get("trial_id")): item for item in judge_calls}
    groups: dict[str, dict[str, Any]] = {}
    affected = 0
    for trial in trials:
        call = calls.get(str(trial.get("id")))
        metrics = trial.get("metrics") if isinstance(trial.get("metrics"), dict) else {}
        runtime_completed = bool(metrics.get("runtime_completed") or trial.get("output"))
        item = classify_evaluation_failure(
            trial_status=trial.get("status"),
            failure_code=trial.get("failure_code"),
            failure_detail=trial.get("failure_detail"),
            judge_status=call.get("status") if call else None,
            judge_error=call.get("error") if call else None,
            runtime_completed=runtime_completed,
        )
        if item is None:
            continue
        affected += 1
        key = str(item["code"])
        group = groups.setdefault(key, {**item, "count": 0, "trial_ids": []})
        group["count"] += 1
        group["trial_ids"].append(str(trial.get("id")))
    ordered = sorted(
        groups.values(),
        key=lambda value: (-int(value["count"]), str(value["code"])),
    )
    return {
        "affected_trial_count": affected,
        "groups": ordered,
        "primary": ordered[0] if ordered else None,
    }


__all__ = [
    "canonical_judge_failure_code",
    "classify_evaluation_failure",
    "judge_failure_policy",
    "summarize_failures",
]
