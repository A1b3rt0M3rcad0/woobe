from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Any, Iterable

from modules.evaluation.domain.enums import (
    EstimateConfidence,
    EvaluationCheckStatus,
    QualificationStatus,
)


@dataclass(frozen=True)
class DeterministicCheck:
    key: str
    dimension: str
    status: str
    score: float | None
    blocking: bool
    reason: str
    evidence: dict[str, Any]
    weight: float = 1.0


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check(
    *,
    key: str,
    dimension: str,
    passed: bool,
    reason: str,
    evidence: dict[str, Any],
    blocking: bool = False,
    weight: float = 1.0,
) -> DeterministicCheck:
    return DeterministicCheck(
        key=key,
        dimension=dimension,
        status=(
            EvaluationCheckStatus.PASSED.value
            if passed
            else EvaluationCheckStatus.FAILED.value
        ),
        score=100.0 if passed else 0.0,
        blocking=blocking,
        reason=reason,
        evidence=evidence,
        weight=max(float(weight), 0.0),
    )


def _merged_policy(
    expected_contract: dict[str, Any] | None,
    suite_checks: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(suite_checks or {})
    for key, value in (expected_contract or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = {**result[key], **value}
        else:
            result[key] = value
    return result


def evaluate_deterministic_checks(
    expected_contract: dict[str, Any] | None,
    *,
    output: dict[str, Any],
    metrics: dict[str, Any],
    suite_checks: dict[str, Any] | None = None,
) -> list[DeterministicCheck]:
    contract = _merged_policy(expected_contract, suite_checks)
    checks: list[DeterministicCheck] = []
    runtime = contract.get("runtime") if isinstance(contract.get("runtime"), dict) else {}
    tools = contract.get("tools") if isinstance(contract.get("tools"), dict) else {}
    network = contract.get("network") if isinstance(contract.get("network"), dict) else {}
    output_contract = (
        contract.get("output_contract")
        if isinstance(contract.get("output_contract"), dict)
        else {}
    )
    weights = contract.get("weights") if isinstance(contract.get("weights"), dict) else {}

    answer = output.get("answer")
    if bool(output_contract.get("required", True)):
        passed = isinstance(answer, str) and bool(answer.strip())
        checks.append(
            _check(
                key="non_empty_output",
                dimension="reliability",
                passed=passed,
                reason="The target returned a public result." if passed else "The target returned no public result.",
                evidence={"answer_length": len(answer or "")},
                blocking=True,
                weight=weights.get("reliability", 1),
            )
        )

    if output_contract.get("json_required"):
        passed = isinstance(output.get("parsed_output"), dict)
        checks.append(
            _check(
                key="valid_json_output",
                dimension="contract",
                passed=passed,
                reason="Output satisfies the structured JSON requirement." if passed else "Output is not valid structured JSON.",
                evidence={"parse_error": output.get("output_parse_error")},
                blocking=bool(output_contract.get("blocking", True)),
                weight=weights.get("contract", 1),
            )
        )

    latency = _number(metrics.get("latency_ms"))
    max_latency = _number(runtime.get("max_latency_ms"))
    if max_latency is not None:
        passed = latency is not None and latency <= max_latency
        checks.append(
            _check(
                key="max_latency_ms",
                dimension="performance",
                passed=passed,
                reason="Latency is within the configured limit." if passed else "Latency is missing or exceeds the configured limit.",
                evidence={"latency_ms": latency, "limit_ms": max_latency},
                blocking=bool(runtime.get("latency_blocking", False)),
                weight=weights.get("performance", 1),
            )
        )

    cost = _number(metrics.get("cost_usd"))
    max_cost = _number(runtime.get("max_cost_usd"))
    if max_cost is not None:
        passed = cost is not None and cost <= max_cost
        checks.append(
            _check(
                key="max_cost_usd",
                dimension="cost",
                passed=passed,
                reason="Cost is within the configured limit." if passed else "Cost is unknown or exceeds the configured limit.",
                evidence={"cost_usd": cost, "limit_usd": max_cost},
                blocking=bool(runtime.get("cost_blocking", False)),
                weight=weights.get("cost", 1),
            )
        )

    if runtime.get("fallback_allowed") is False:
        fallback = metrics.get("fallback_used")
        passed = fallback is False
        checks.append(
            _check(
                key="fallback_forbidden",
                dimension="reliability",
                passed=passed,
                reason="No fallback model was used." if passed else "Fallback use is unknown or forbidden.",
                evidence={"fallback_used": fallback},
                blocking=bool(runtime.get("fallback_blocking", True)),
                weight=weights.get("reliability", 1),
            )
        )

    raw_calls = output.get("tool_calls")
    tool_calls = raw_calls if isinstance(raw_calls, list) else []
    tool_names = {
        str(item.get("tool_name") or item.get("name"))
        for item in tool_calls
        if isinstance(item, dict)
    }
    for name in [str(item) for item in tools.get("required", [])]:
        passed = name in tool_names
        checks.append(
            _check(
                key=f"required_tool:{name}",
                dimension="tools",
                passed=passed,
                reason=f"Required Tool {name} was called." if passed else f"Required Tool {name} was not called.",
                evidence={"tool_name": name, "tool_calls": sorted(tool_names)},
                blocking=bool(tools.get("required_blocking", True)),
                weight=weights.get("tools", 1),
            )
        )
    for name in [str(item) for item in tools.get("forbidden", [])]:
        passed = name not in tool_names
        checks.append(
            _check(
                key=f"forbidden_tool:{name}",
                dimension="tools",
                passed=passed,
                reason=f"Forbidden Tool {name} was not called." if passed else f"Forbidden Tool {name} was called.",
                evidence={"tool_name": name, "tool_calls": sorted(tool_names)},
                blocking=bool(tools.get("forbidden_blocking", True)),
                weight=weights.get("tools", 1),
            )
        )
    if isinstance(tools.get("max_calls"), int):
        limit = int(tools["max_calls"])
        checks.append(
            _check(
                key="max_tool_calls",
                dimension="tools",
                passed=len(tool_calls) <= limit,
                reason="Tool call count is within the limit." if len(tool_calls) <= limit else "Tool call count exceeds the limit.",
                evidence={"tool_call_count": len(tool_calls), "limit": limit},
                blocking=bool(tools.get("max_calls_blocking", False)),
                weight=weights.get("tools", 1),
            )
        )

    if isinstance(network.get("max_agent_runs"), int):
        observed = int(metrics.get("agent_run_count") or 0)
        limit = int(network["max_agent_runs"])
        checks.append(
            _check(
                key="max_network_agent_runs",
                dimension="network",
                passed=observed <= limit,
                reason="Network fan-out is within the limit." if observed <= limit else "Network fan-out exceeds the limit.",
                evidence={"agent_run_count": observed, "limit": limit},
                blocking=bool(network.get("max_agent_runs_blocking", False)),
                weight=weights.get("network", 1),
            )
        )
    return checks


def calculate_trial_score(
    *,
    judge_result: dict[str, Any],
    deterministic: list[DeterministicCheck],
    case_minimum: float,
    judge_weight: float = 4.0,
    case_blocking: bool = False,
) -> dict[str, Any]:
    components: list[tuple[float, float]] = []
    judge_score = _number(judge_result.get("score"))
    if judge_score is not None:
        components.append((judge_score, max(judge_weight, 0.0)))
    components.extend(
        (float(item.score), max(float(item.weight), 0.0))
        for item in deterministic
        if item.score is not None
    )
    denominator = sum(weight for _, weight in components)
    final_score = (
        sum(score * weight for score, weight in components) / denominator
        if denominator > 0
        else None
    )
    blocking_failures = [
        item for item in deterministic if item.blocking and item.status == "failed"
    ]
    passed = (
        final_score is not None
        and final_score >= case_minimum
        and judge_result.get("status") in {"passed", "passed_with_warnings"}
        and not blocking_failures
    )
    if case_blocking and not passed and not blocking_failures:
        blocking_failures = [
            DeterministicCheck(
                key="case_blocking_failure",
                dimension="case",
                status="failed",
                score=0,
                blocking=True,
                reason="The blocking Test Case did not pass.",
                evidence={},
            )
        ]
    return {
        "score": final_score,
        "passed": passed,
        "blocking_failures": blocking_failures,
        "warnings": [
            item for item in deterministic if not item.blocking and item.status == "failed"
        ],
    }


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


def summarize_values(values: Iterable[float | int | None]) -> dict[str, float | int | None]:
    normalized = [float(value) for value in values if value is not None]
    if not normalized:
        return {"n": 0, "mean": None, "median": None, "stddev": None, "p25": None, "p90": None, "p95": None}
    return {
        "n": len(normalized),
        "mean": mean(normalized),
        "median": median(normalized),
        "stddev": pstdev(normalized) if len(normalized) >= 2 else None,
        "p25": _percentile(normalized, 0.25),
        "p90": _percentile(normalized, 0.90),
        "p95": _percentile(normalized, 0.95) if len(normalized) >= 20 else None,
    }


def _trial_weight(item: dict[str, Any]) -> float:
    metrics = item.get("metrics") or {}
    base = max(float(metrics.get("case_weight") or 1.0), 0.0)
    frequency = metrics.get("production_frequency")
    return base * (max(float(frequency), 0.0) if frequency is not None else 1.0)


def _weighted_average(items: list[dict[str, Any]], key: str) -> float | None:
    pairs = [
        (float(item[key]), _trial_weight(item))
        for item in items
        if item.get(key) is not None and _trial_weight(item) > 0
    ]
    denominator = sum(weight for _, weight in pairs)
    return sum(value * weight for value, weight in pairs) / denominator if denominator else None


def _regression_percent(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None or baseline == 0:
        return None
    return (candidate - baseline) / abs(baseline) * 100.0


def aggregate_evaluation(
    trials: list[dict[str, Any]],
    acceptance_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    policy = acceptance_policy or {}
    completed = [item for item in trials if item.get("status") == "completed"]
    scored = [item for item in completed if item.get("score") is not None]
    total_weight = sum(_trial_weight(item) for item in trials)
    passed_weight = sum(_trial_weight(item) for item in completed if item.get("passed") is True)
    pass_rate = passed_weight / total_weight * 100 if total_weight else 0.0
    overall_score = _weighted_average(scored, "score")
    critical_failures = sum(int(item.get("critical_failures") or 0) for item in trials)
    warning_count = sum(int(item.get("warning_count") or 0) for item in trials)

    if not scored or len(completed) != len(trials):
        qualification = QualificationStatus.INCONCLUSIVE.value
    elif critical_failures:
        qualification = QualificationStatus.NOT_QUALIFIED.value
    elif overall_score is not None and overall_score >= float(policy.get("minimum_score", 70)) and pass_rate >= float(policy.get("minimum_pass_rate", 80)):
        qualification = QualificationStatus.QUALIFIED_WITH_WARNINGS.value if warning_count else QualificationStatus.QUALIFIED.value
    else:
        qualification = QualificationStatus.NOT_QUALIFIED.value

    by_side: dict[str, dict[str, Any]] = {}
    for side in {str(item.get("side")) for item in trials}:
        values = [item for item in trials if item.get("side") == side]
        by_side[side] = {
            "score": summarize_values([item.get("score") for item in values]),
            "latency_ms": summarize_values([(item.get("metrics") or {}).get("latency_ms") for item in values]),
            "cost_usd": summarize_values([(item.get("metrics") or {}).get("cost_usd") for item in values]),
            "pass_rate": sum(1 for item in values if item.get("passed") is True) / len(values) * 100 if values else 0,
            "critical_failures": sum(int(item.get("critical_failures") or 0) for item in values),
        }

    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for item in trials:
        pairs.setdefault(str(item.get("pair_key")), {})[str(item.get("side"))] = item
    deltas: list[dict[str, Any]] = []
    for pair_key, pair in pairs.items():
        candidate = pair.get("candidate")
        baseline = pair.get("baseline")
        if not candidate or not baseline:
            continue
        cm, bm = candidate.get("metrics") or {}, baseline.get("metrics") or {}
        deltas.append({
            "pair_key": pair_key,
            "score_delta": float(candidate["score"]) - float(baseline["score"]) if candidate.get("score") is not None and baseline.get("score") is not None else None,
            "latency_delta_ms": float(cm["latency_ms"]) - float(bm["latency_ms"]) if cm.get("latency_ms") is not None and bm.get("latency_ms") is not None else None,
            "cost_delta_usd": float(cm["cost_usd"]) - float(bm["cost_usd"]) if cm.get("cost_usd") is not None and bm.get("cost_usd") is not None else None,
        })

    comparison = None
    if deltas:
        score_deltas = [item["score_delta"] for item in deltas if item["score_delta"] is not None]
        candidate_side = by_side.get("candidate", {})
        baseline_side = by_side.get("baseline", {})
        candidate_latency = (candidate_side.get("latency_ms") or {}).get("median")
        baseline_latency = (baseline_side.get("latency_ms") or {}).get("median")
        candidate_cost = (candidate_side.get("cost_usd") or {}).get("median")
        baseline_cost = (baseline_side.get("cost_usd") or {}).get("median")
        policy_failures: list[str] = []
        minimum_n = int(policy.get("minimum_paired_n", 1))
        if len(score_deltas) < minimum_n:
            policy_failures.append(f"paired_n_below_{minimum_n}")
        maximum_score_regression = _number(policy.get("maximum_score_regression"))
        score_mean = mean(score_deltas) if score_deltas else None
        if maximum_score_regression is not None and score_mean is not None and score_mean < -abs(maximum_score_regression):
            policy_failures.append("score_regression_exceeded")
        latency_regression = _regression_percent(candidate_latency, baseline_latency)
        maximum_latency = _number(policy.get("maximum_latency_regression_percent"))
        if maximum_latency is not None and latency_regression is not None and latency_regression > maximum_latency:
            policy_failures.append("latency_regression_exceeded")
        cost_regression = _regression_percent(candidate_cost, baseline_cost)
        maximum_cost = _number(policy.get("maximum_cost_regression_percent"))
        if maximum_cost is not None and cost_regression is not None and cost_regression > maximum_cost:
            policy_failures.append("cost_regression_exceeded")
        comparison = {
            "paired_n": len(deltas),
            "score_delta": summarize_values(score_deltas),
            "latency_delta_ms": summarize_values([item["latency_delta_ms"] for item in deltas]),
            "cost_delta_usd": summarize_values([item["cost_delta_usd"] for item in deltas]),
            "candidate_wins": sum(1 for value in score_deltas if value > 0),
            "baseline_wins": sum(1 for value in score_deltas if value < 0),
            "ties": sum(1 for value in score_deltas if value == 0),
            "latency_regression_percent": latency_regression,
            "cost_regression_percent": cost_regression,
            "policy_passed": not policy_failures,
            "policy_failures": policy_failures,
        }
        if policy_failures and qualification not in {QualificationStatus.INCONCLUSIVE.value, QualificationStatus.NOT_QUALIFIED.value}:
            qualification = QualificationStatus.NOT_QUALIFIED.value

    return {
        "qualification_status": qualification,
        "overall_score": overall_score,
        "pass_rate": pass_rate,
        "critical_failures": critical_failures,
        "trial_count": len(trials),
        "completed_trial_count": len(completed),
        "by_side": by_side,
        "comparison": comparison,
    }


def build_estimate(*, values: list[dict[str, Any]], volume: int, target_type: str) -> dict[str, Any]:
    costs = [_number((item.get("metrics") or {}).get("cost_usd")) for item in values]
    costs = [value for value in costs if value is not None]
    latencies = [_number((item.get("metrics") or {}).get("latency_ms")) for item in values]
    latencies = [value for value in latencies if value is not None]
    fanout = [_number((item.get("metrics") or {}).get("agent_run_count")) for item in values]
    fanout = [value for value in fanout if value is not None]
    limitations: list[str] = []
    if not costs:
        limitations.append("Target Run cost is unknown because pricing coverage is incomplete.")
    if len(values) < 5:
        limitations.append("Fewer than five completed Trials; projection stability is low.")
    if target_type == "network" and not fanout:
        limitations.append("Network Agent Run fan-out was unavailable.")
    confidence = EstimateConfidence.INSUFFICIENT_DATA.value if not values else EstimateConfidence.LOW.value if len(values) < 5 or not costs else EstimateConfidence.MEDIUM.value if len(values) < 20 else EstimateConfidence.HIGH.value
    cost_summary = summarize_values(costs)
    latency_summary = summarize_values(latencies)
    fanout_summary = summarize_values(fanout)
    projected = lambda value: float(value) * volume if value is not None else None
    return {
        "confidence": confidence,
        "limitations": limitations,
        "observation_summary": {
            "sample_size": len(values),
            "cost_usd": cost_summary,
            "latency_ms": latency_summary,
            "agent_run_count": fanout_summary,
            "pricing_coverage": {
                "known": len(costs),
                "total": len(values),
            },
        },
        "scenarios": {
            "optimistic": {"provider_cost_usd": projected(cost_summary.get("p25")), "latency_ms_per_run": latency_summary.get("p25"), "agent_runs": projected(fanout_summary.get("p25")) if target_type == "network" else volume},
            "expected": {"provider_cost_usd": projected(cost_summary.get("median")), "latency_ms_per_run": latency_summary.get("median"), "agent_runs": projected(fanout_summary.get("median")) if target_type == "network" else volume},
            "conservative": {"provider_cost_usd": projected(cost_summary.get("p90")), "latency_ms_per_run": latency_summary.get("p90"), "agent_runs": projected(fanout_summary.get("p90")) if target_type == "network" else volume},
        },
    }
