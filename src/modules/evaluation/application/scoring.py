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
        weight=weight,
    )


def evaluate_deterministic_checks(
    expected_contract: dict[str, Any] | None,
    *,
    output: dict[str, Any],
    metrics: dict[str, Any],
) -> list[DeterministicCheck]:
    contract = expected_contract or {}
    checks: list[DeterministicCheck] = []
    runtime = contract.get("runtime") if isinstance(contract.get("runtime"), dict) else {}
    tools = contract.get("tools") if isinstance(contract.get("tools"), dict) else {}
    network = contract.get("network") if isinstance(contract.get("network"), dict) else {}
    output_contract = (
        contract.get("output_contract")
        if isinstance(contract.get("output_contract"), dict)
        else {}
    )

    answer = output.get("answer")
    require_non_empty = bool(output_contract.get("required", True))
    if require_non_empty:
        non_empty = isinstance(answer, str) and bool(answer.strip())
        checks.append(
            _check(
                key="non_empty_output",
                dimension="reliability",
                passed=non_empty,
                reason="The target returned a public result." if non_empty else "The target returned no public result.",
                evidence={"answer_length": len(answer or "")},
                blocking=True,
            )
        )

    if output_contract.get("json_required"):
        parsed = output.get("parsed_output")
        valid = isinstance(parsed, dict)
        checks.append(
            _check(
                key="valid_json_output",
                dimension="contract",
                passed=valid,
                reason="Output satisfies the structured JSON requirement." if valid else "Output is not valid structured JSON.",
                evidence={"parse_error": output.get("output_parse_error")},
                blocking=bool(output_contract.get("blocking", True)),
            )
        )

    max_latency = _number(runtime.get("max_latency_ms"))
    latency = _number(metrics.get("latency_ms"))
    if max_latency is not None:
        passed = latency is not None and latency <= max_latency
        checks.append(
            _check(
                key="max_latency_ms",
                dimension="performance",
                passed=passed,
                reason=(
                    f"Latency {latency:.0f} ms is within the {max_latency:.0f} ms limit."
                    if passed and latency is not None
                    else f"Latency is missing or exceeds the {max_latency:.0f} ms limit."
                ),
                evidence={"latency_ms": latency, "limit_ms": max_latency},
                blocking=bool(runtime.get("latency_blocking", False)),
            )
        )

    max_cost = _number(runtime.get("max_cost_usd"))
    cost = _number(metrics.get("cost_usd"))
    if max_cost is not None:
        passed = cost is not None and cost <= max_cost
        checks.append(
            _check(
                key="max_cost_usd",
                dimension="cost",
                passed=passed,
                reason=(
                    f"Cost ${cost:.6f} is within the ${max_cost:.6f} limit."
                    if passed and cost is not None
                    else "Cost is unknown or exceeds the configured limit."
                ),
                evidence={"cost_usd": cost, "limit_usd": max_cost},
                blocking=bool(runtime.get("cost_blocking", False)),
            )
        )

    if runtime.get("fallback_allowed") is False:
        fallback_used = bool(metrics.get("fallback_used"))
        checks.append(
            _check(
                key="fallback_forbidden",
                dimension="reliability",
                passed=not fallback_used,
                reason="No fallback model was used." if not fallback_used else "A fallback model was used but the Suite forbids it.",
                evidence={"fallback_used": fallback_used},
                blocking=bool(runtime.get("fallback_blocking", True)),
            )
        )

    raw_tool_calls = output.get("tool_calls")
    tool_calls = raw_tool_calls if isinstance(raw_tool_calls, list) else []
    tool_names = [str(item.get("tool_name")) for item in tool_calls if isinstance(item, dict)]
    required_tools = [str(item) for item in tools.get("required", [])]
    forbidden_tools = [str(item) for item in tools.get("forbidden", [])]
    for tool_name in required_tools:
        called = tool_name in tool_names
        checks.append(
            _check(
                key=f"required_tool:{tool_name}",
                dimension="tools",
                passed=called,
                reason=f"Required Tool {tool_name} was called." if called else f"Required Tool {tool_name} was not called.",
                evidence={"tool_name": tool_name, "tool_calls": tool_names},
                blocking=bool(tools.get("required_blocking", True)),
            )
        )
    for tool_name in forbidden_tools:
        called = tool_name in tool_names
        checks.append(
            _check(
                key=f"forbidden_tool:{tool_name}",
                dimension="tools",
                passed=not called,
                reason=f"Forbidden Tool {tool_name} was not called." if not called else f"Forbidden Tool {tool_name} was called.",
                evidence={"tool_name": tool_name, "tool_calls": tool_names},
                blocking=bool(tools.get("forbidden_blocking", True)),
            )
        )

    max_tool_calls = tools.get("max_calls")
    if isinstance(max_tool_calls, int):
        passed = len(tool_calls) <= max_tool_calls
        checks.append(
            _check(
                key="max_tool_calls",
                dimension="tools",
                passed=passed,
                reason=f"Tool call count {len(tool_calls)} is within the limit." if passed else f"Tool call count {len(tool_calls)} exceeds the limit {max_tool_calls}.",
                evidence={"tool_call_count": len(tool_calls), "limit": max_tool_calls},
                blocking=bool(tools.get("max_calls_blocking", False)),
            )
        )

    max_agent_runs = network.get("max_agent_runs")
    observed_agent_runs = metrics.get("agent_run_count")
    if isinstance(max_agent_runs, int):
        observed = int(observed_agent_runs or 0)
        passed = observed <= max_agent_runs
        checks.append(
            _check(
                key="max_network_agent_runs",
                dimension="network",
                passed=passed,
                reason=f"Network used {observed} Agent Runs, within the limit." if passed else f"Network used {observed} Agent Runs, exceeding the limit {max_agent_runs}.",
                evidence={"agent_run_count": observed, "limit": max_agent_runs},
                blocking=bool(network.get("max_agent_runs_blocking", False)),
            )
        )

    return checks


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


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


def aggregate_evaluation(
    trials: list[dict[str, Any]],
    acceptance_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    policy = acceptance_policy or {}
    completed = [item for item in trials if item.get("status") == "completed"]
    scored = [item for item in completed if item.get("score") is not None]
    total = len(trials)
    passed_count = sum(1 for item in completed if item.get("passed") is True)
    pass_rate = (passed_count / total * 100.0) if total else 0.0
    scores = [float(item["score"]) for item in scored]
    critical_failures = sum(int(item.get("critical_failures") or 0) for item in trials)
    overall_score = mean(scores) if scores else None
    minimum_score = float(policy.get("minimum_score", 70))
    minimum_pass_rate = float(policy.get("minimum_pass_rate", 80))

    if not scored or len(completed) != total:
        qualification = QualificationStatus.INCONCLUSIVE.value
    elif critical_failures > 0:
        qualification = QualificationStatus.NOT_QUALIFIED.value
    elif overall_score is not None and overall_score >= minimum_score and pass_rate >= minimum_pass_rate:
        warning_count = sum(int(item.get("warning_count") or 0) for item in trials)
        qualification = (
            QualificationStatus.QUALIFIED_WITH_WARNINGS.value
            if warning_count
            else QualificationStatus.QUALIFIED.value
        )
    else:
        qualification = QualificationStatus.NOT_QUALIFIED.value

    by_side: dict[str, dict[str, Any]] = {}
    for side in {str(item.get("side")) for item in trials}:
        side_trials = [item for item in trials if item.get("side") == side]
        by_side[side] = {
            "score": summarize_values([item.get("score") for item in side_trials]),
            "latency_ms": summarize_values([(item.get("metrics") or {}).get("latency_ms") for item in side_trials]),
            "cost_usd": summarize_values([(item.get("metrics") or {}).get("cost_usd") for item in side_trials]),
            "pass_rate": (
                sum(1 for item in side_trials if item.get("passed") is True)
                / len(side_trials)
                * 100.0
                if side_trials
                else 0.0
            ),
            "critical_failures": sum(int(item.get("critical_failures") or 0) for item in side_trials),
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
        candidate_metrics = candidate.get("metrics") or {}
        baseline_metrics = baseline.get("metrics") or {}
        score_delta = None
        if candidate.get("score") is not None and baseline.get("score") is not None:
            score_delta = float(candidate["score"]) - float(baseline["score"])
        latency_delta = None
        if candidate_metrics.get("latency_ms") is not None and baseline_metrics.get("latency_ms") is not None:
            latency_delta = float(candidate_metrics["latency_ms"]) - float(baseline_metrics["latency_ms"])
        cost_delta = None
        if candidate_metrics.get("cost_usd") is not None and baseline_metrics.get("cost_usd") is not None:
            cost_delta = float(candidate_metrics["cost_usd"]) - float(baseline_metrics["cost_usd"])
        deltas.append(
            {
                "pair_key": pair_key,
                "score_delta": score_delta,
                "latency_delta_ms": latency_delta,
                "cost_delta_usd": cost_delta,
                "candidate_passed": candidate.get("passed"),
                "baseline_passed": baseline.get("passed"),
            }
        )

    comparison = None
    if deltas:
        score_deltas = [item["score_delta"] for item in deltas if item["score_delta"] is not None]
        comparison = {
            "paired_n": len(deltas),
            "score_delta": summarize_values(score_deltas),
            "latency_delta_ms": summarize_values([item["latency_delta_ms"] for item in deltas]),
            "cost_delta_usd": summarize_values([item["cost_delta_usd"] for item in deltas]),
            "candidate_wins": sum(1 for value in score_deltas if value > 0),
            "baseline_wins": sum(1 for value in score_deltas if value < 0),
            "ties": sum(1 for value in score_deltas if value == 0),
        }

    return {
        "qualification_status": qualification,
        "overall_score": overall_score,
        "pass_rate": pass_rate,
        "critical_failures": critical_failures,
        "trial_count": total,
        "completed_trial_count": len(completed),
        "by_side": by_side,
        "comparison": comparison,
    }


def build_estimate(
    *,
    values: list[dict[str, Any]],
    volume: int,
    target_type: str,
) -> dict[str, Any]:
    costs = [
        _number((item.get("metrics") or {}).get("cost_usd"))
        for item in values
    ]
    costs = [value for value in costs if value is not None]
    latencies = [
        _number((item.get("metrics") or {}).get("latency_ms"))
        for item in values
    ]
    latencies = [value for value in latencies if value is not None]
    agent_run_counts = [
        _number((item.get("metrics") or {}).get("agent_run_count"))
        for item in values
    ]
    agent_run_counts = [value for value in agent_run_counts if value is not None]
    limitations: list[str] = []
    if not costs:
        limitations.append("Target Run cost could not be measured because token usage or pricing is incomplete.")
    if len(values) < 5:
        limitations.append("Fewer than five completed Trials; projections have low statistical stability.")
    if target_type == "network" and not agent_run_counts:
        limitations.append("Network Agent Run fan-out was unavailable for projection.")

    confidence = (
        EstimateConfidence.INSUFFICIENT_DATA.value
        if not values
        else EstimateConfidence.LOW.value
        if len(values) < 5 or not costs
        else EstimateConfidence.MEDIUM.value
        if len(values) < 20
        else EstimateConfidence.HIGH.value
    )
    cost_summary = summarize_values(costs)
    latency_summary = summarize_values(latencies)
    fanout_summary = summarize_values(agent_run_counts)

    def projected(value: float | int | None) -> float | None:
        return float(value) * volume if value is not None else None

    scenarios = {
        "optimistic": {
            "provider_cost_usd": projected(cost_summary.get("p25")),
            "latency_ms_per_run": latency_summary.get("p25"),
            "agent_runs": projected(fanout_summary.get("p25")) if target_type == "network" else volume,
        },
        "expected": {
            "provider_cost_usd": projected(cost_summary.get("median")),
            "latency_ms_per_run": latency_summary.get("median"),
            "agent_runs": projected(fanout_summary.get("median")) if target_type == "network" else volume,
        },
        "conservative": {
            "provider_cost_usd": projected(cost_summary.get("p90")),
            "latency_ms_per_run": latency_summary.get("p90"),
            "agent_runs": projected(fanout_summary.get("p90")) if target_type == "network" else volume,
        },
    }
    return {
        "confidence": confidence,
        "limitations": limitations,
        "observation_summary": {
            "sample_size": len(values),
            "cost_usd": cost_summary,
            "latency_ms": latency_summary,
            "agent_run_count": fanout_summary,
        },
        "scenarios": scenarios,
    }
