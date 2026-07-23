from __future__ import annotations

from statistics import mean, median
from typing import Any


DEFAULT_COMPARISON_KPIS: dict[str, dict[str, Any]] = {
    "quality_score": {"weight": 0.50, "direction": "maximize"},
    "pass_rate": {"weight": 0.25, "direction": "maximize"},
    "runtime_cost_usd_per_trial": {"weight": 0.15, "direction": "minimize"},
    "latency_median_ms": {"weight": 0.10, "direction": "minimize"},
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _trial_weight(trial: dict[str, Any]) -> float:
    metrics = trial.get("metrics") if isinstance(trial.get("metrics"), dict) else {}
    case_weight = max(_number(metrics.get("case_weight")) or 1.0, 0.0)
    frequency = _number(metrics.get("production_frequency"))
    return case_weight * (max(frequency, 0.0) if frequency is not None else 1.0)


def _weighted_mean(
    trials: list[dict[str, Any]],
    getter,
) -> float | None:
    pairs: list[tuple[float, float]] = []
    for trial in trials:
        value = _number(getter(trial))
        weight = _trial_weight(trial)
        if value is not None and weight > 0:
            pairs.append((value, weight))
    total = sum(weight for _, weight in pairs)
    if not total:
        return None
    return sum(value * weight for value, weight in pairs) / total


def canonical_evaluation_kpis(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the reusable KPI contract for one immutable evidence revision."""

    completed = [trial for trial in trials if trial.get("status") == "completed"]
    conclusive = [
        trial
        for trial in completed
        if trial.get("score") is not None and trial.get("passed") is not None
    ]
    quality_score = _weighted_mean(conclusive, lambda item: item.get("score"))
    passed_weight = sum(_trial_weight(item) for item in conclusive if item.get("passed") is True)
    conclusive_weight = sum(_trial_weight(item) for item in conclusive)
    pass_rate = passed_weight / conclusive_weight * 100 if conclusive_weight else None

    runtime_costs = [
        value
        for trial in trials
        if (value := _number((trial.get("metrics") or {}).get("cost_usd"))) is not None
    ]
    latencies = [
        value
        for trial in trials
        if (value := _number((trial.get("metrics") or {}).get("latency_ms"))) is not None
    ]
    input_tokens = [
        value
        for trial in trials
        if (value := _number((trial.get("metrics") or {}).get("input_tokens"))) is not None
    ]
    output_tokens = [
        value
        for trial in trials
        if (value := _number((trial.get("metrics") or {}).get("output_tokens"))) is not None
    ]
    tool_calls = [
        value
        for trial in trials
        if (value := _number((trial.get("metrics") or {}).get("tool_call_count"))) is not None
    ]

    groups: dict[str, list[dict[str, Any]]] = {}
    for trial in trials:
        key = str(trial.get("test_case_id") or str(trial.get("pair_key") or "").split(":", 1)[0])
        groups.setdefault(key, []).append(trial)
    stable = 0
    mixed = 0
    failed = 0
    inconclusive = 0
    for values in groups.values():
        outcomes = [item.get("passed") for item in values]
        if any(value is None for value in outcomes):
            inconclusive += 1
        elif outcomes and all(value is True for value in outcomes):
            stable += 1
        elif outcomes and all(value is False for value in outcomes):
            failed += 1
        else:
            mixed += 1

    session_trials = [
        item
        for item in trials
        if (item.get("metrics") or {}).get("interaction_mode") == "session"
    ]
    completed_sessions = sum(
        1 for item in session_trials if bool((item.get("metrics") or {}).get("session_completed"))
    )
    turn_total = sum(int((item.get("metrics") or {}).get("turn_count") or 0) for item in session_trials)
    turn_completed = sum(
        int((item.get("metrics") or {}).get("completed_turn_count") or 0)
        for item in session_trials
    )
    session_costs = [
        value
        for item in session_trials
        if (value := _number((item.get("metrics") or {}).get("cost_usd"))) is not None
    ]
    session_latencies = [
        value
        for item in session_trials
        if (value := _number((item.get("metrics") or {}).get("latency_ms"))) is not None
    ]
    session_tokens = [
        value
        for item in session_trials
        if (
            value := (
                (_number((item.get("metrics") or {}).get("input_tokens")) or 0)
                + (_number((item.get("metrics") or {}).get("output_tokens")) or 0)
            )
        ) > 0
    ]

    case_count = len(groups)
    return {
        "schema_version": "evaluation-kpis-v1",
        "quality_score": quality_score,
        "pass_rate": pass_rate,
        "sample_size": len(trials),
        "conclusive_trial_count": len(conclusive),
        "inconclusive_trial_count": max(0, len(trials) - len(conclusive)),
        "runtime_cost_usd_total": sum(runtime_costs) if runtime_costs else None,
        "runtime_cost_usd_per_trial": mean(runtime_costs) if runtime_costs else None,
        "runtime_pricing_coverage_percent": len(runtime_costs) / len(trials) * 100 if trials else 0.0,
        "latency_median_ms": median(latencies) if latencies else None,
        "latency_p90_ms": _percentile(latencies, 0.90),
        "input_tokens_mean": mean(input_tokens) if input_tokens else None,
        "output_tokens_mean": mean(output_tokens) if output_tokens else None,
        "tool_calls_mean": mean(tool_calls) if tool_calls else None,
        "case_count": case_count,
        "stable_case_count": stable,
        "mixed_case_count": mixed,
        "failed_case_count": failed,
        "inconclusive_case_count": inconclusive,
        "stable_case_rate": stable / case_count * 100 if case_count else None,
        "session": {
            "session_count": len(session_trials),
            "session_completion_rate": (
                completed_sessions / len(session_trials) * 100 if session_trials else None
            ),
            "turn_count": turn_total,
            "turn_completion_rate": (
                turn_completed / turn_total * 100 if turn_total else None
            ),
            "average_turns_per_session": (
                turn_total / len(session_trials) if session_trials else None
            ),
            "cost_usd_per_session": mean(session_costs) if session_costs else None,
            "cost_usd_per_turn": (
                sum(session_costs) / turn_total if session_costs and turn_total else None
            ),
            "latency_ms_per_session": median(session_latencies) if session_latencies else None,
            "latency_ms_per_turn": (
                sum(session_latencies) / turn_total
                if session_latencies and turn_total
                else None
            ),
            "tokens_per_session": mean(session_tokens) if session_tokens else None,
        },
    }


def comparison_kpi_policy(acceptance_policy: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = (acceptance_policy or {}).get("comparison_kpis")
    if not isinstance(raw, dict):
        return {key: dict(value) for key, value in DEFAULT_COMPARISON_KPIS.items()}
    result: dict[str, dict[str, Any]] = {}
    for key, default in DEFAULT_COMPARISON_KPIS.items():
        configured = raw.get(key)
        configured = configured if isinstance(configured, dict) else {}
        try:
            weight = max(0.0, float(configured.get("weight", default["weight"])))
        except (TypeError, ValueError):
            weight = float(default["weight"])
        direction = str(configured.get("direction") or default["direction"])
        if direction not in {"maximize", "minimize"}:
            direction = str(default["direction"])
        result[key] = {"weight": weight, "direction": direction}
    return result


def calculate_comparison_winner(
    candidate: dict[str, Any],
    reference: dict[str, Any],
    *,
    acceptance_policy: dict[str, Any] | None,
    authoritative: bool,
) -> dict[str, Any]:
    policy = comparison_kpi_policy(acceptance_policy)
    candidate_points = 0.0
    reference_points = 0.0
    available_weight = 0.0
    results: list[dict[str, Any]] = []

    for key, config in policy.items():
        candidate_value = _number(candidate.get(key))
        reference_value = _number(reference.get(key))
        weight = float(config["weight"])
        direction = str(config["direction"])
        winner: str | None = None
        if candidate_value is not None and reference_value is not None and weight > 0:
            available_weight += weight
            tolerance = max(abs(candidate_value), abs(reference_value), 1.0) * 1e-6
            delta = candidate_value - reference_value
            if abs(delta) <= tolerance:
                winner = "tie"
                candidate_points += weight / 2
                reference_points += weight / 2
            else:
                candidate_better = delta > 0 if direction == "maximize" else delta < 0
                winner = "candidate" if candidate_better else "reference"
                if candidate_better:
                    candidate_points += weight
                else:
                    reference_points += weight
        else:
            delta = (
                candidate_value - reference_value
                if candidate_value is not None and reference_value is not None
                else None
            )
        results.append(
            {
                "key": key,
                "direction": direction,
                "weight": weight,
                "candidate": candidate_value,
                "reference": reference_value,
                "delta": delta,
                "winner": winner,
            }
        )

    if available_weight <= 0:
        side = None
    elif abs(candidate_points - reference_points) <= 1e-9:
        side = "tie"
    else:
        side = "candidate" if candidate_points > reference_points else "reference"
    return {
        "schema_version": "comparison-winner-v1",
        "side": side,
        "candidate_score": candidate_points / available_weight if available_weight else None,
        "reference_score": reference_points / available_weight if available_weight else None,
        "available_weight": available_weight,
        "authoritative": bool(authoritative and side is not None),
        "confidence": "authoritative" if authoritative and side is not None else "indicative",
        "kpis": results,
        "policy": policy,
    }


__all__ = [
    "DEFAULT_COMPARISON_KPIS",
    "calculate_comparison_winner",
    "canonical_evaluation_kpis",
    "comparison_kpi_policy",
]
