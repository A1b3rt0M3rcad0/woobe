from __future__ import annotations

from typing import Any


def _text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


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

    judge_failed = (
        code.startswith("judge_")
        or judge_status == "failed"
        or "judge" in combined
        or "evaluator model" in combined
    )
    if judge_failed:
        if any(value in combined for value in ("insufficient balance", "insufficient credits", "insufficient_quota")):
            resolved = "judge_insufficient_balance"
            action = "Restore provider balance or choose another active Judge Model, then resume."
            recoverability = "user_action_required"
        elif any(value in combined for value in ("invalid json", "json decode", "structured response")):
            resolved = "judge_invalid_json"
            action = "Retry Judgments with the adaptive structured-output fallback."
            recoverability = "retryable"
        elif any(value in combined for value in ("length", "max_tokens", "output token")):
            resolved = "judge_output_length_limit"
            action = "Retry Judgments with a larger automatic output budget."
            recoverability = "retryable"
        elif any(value in combined for value in ("rate limit", "429")):
            resolved = "judge_rate_limited"
            action = "Resume after the provider rate limit clears."
            recoverability = "retryable"
        elif any(value in combined for value in ("timeout", "timed out")):
            resolved = "judge_timeout"
            action = "Retry only the affected Judgments."
            recoverability = "retryable"
        elif any(value in combined for value in ("credential", "unauthorized", "401", "403")):
            resolved = "judge_credential_invalid"
            action = "Activate a valid Project Credential for the Judge Model."
            recoverability = "user_action_required"
        else:
            resolved = code if code.startswith("judge_") else "judge_unknown_failure"
            action = "Review the persisted Judge error and retry only affected outputs."
            recoverability = "review_required"
        return {
            "stage": "judge",
            "kind": "judge",
            "code": resolved,
            "recoverability": recoverability,
            "recommended_action": action,
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


def summarize_failures(trials: list[dict[str, Any]], judge_calls: list[dict[str, Any]]) -> dict[str, Any]:
    calls = {str(item.get("trial_id")): item for item in judge_calls}
    groups: dict[str, dict[str, Any]] = {}
    affected = 0
    for trial in trials:
        call = calls.get(str(trial.get("id")))
        metrics = trial.get("metrics") if isinstance(trial.get("metrics"), dict) else {}
        item = classify_evaluation_failure(
            trial_status=trial.get("status"),
            failure_code=trial.get("failure_code"),
            failure_detail=trial.get("failure_detail"),
            judge_status=call.get("status") if call else None,
            judge_error=call.get("error") if call else None,
            runtime_completed=bool(metrics.get("runtime_completed")),
        )
        if item is None:
            continue
        affected += 1
        key = str(item["code"])
        group = groups.setdefault(key, {**item, "count": 0, "trial_ids": []})
        group["count"] += 1
        group["trial_ids"].append(str(trial.get("id")))
    ordered = sorted(groups.values(), key=lambda value: (-int(value["count"]), str(value["code"])))
    return {
        "affected_trial_count": affected,
        "groups": ordered,
        "primary": ordered[0] if ordered else None,
    }


__all__ = ["classify_evaluation_failure", "summarize_failures"]
