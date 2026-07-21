from modules.evaluation.application.scoring import (
    aggregate_evaluation,
    build_estimate,
    evaluate_deterministic_checks,
)


def test_blocking_deterministic_failure_cannot_be_hidden_by_score() -> None:
    checks = evaluate_deterministic_checks(
        {
            "output_contract": {"required": True},
            "tools": {"forbidden": ["delete_order"]},
        },
        output={
            "answer": "Order deleted",
            "tool_calls": [{"tool_name": "delete_order"}],
        },
        metrics={"latency_ms": 200, "cost_usd": 0.01},
    )

    forbidden = next(item for item in checks if item.key == "forbidden_tool:delete_order")
    assert forbidden.status == "failed"
    assert forbidden.blocking is True
    assert forbidden.score == 0.0


def test_comparison_aggregates_paired_score_deltas() -> None:
    result = aggregate_evaluation(
        [
            {
                "pair_key": "case-1:1",
                "side": "candidate",
                "status": "completed",
                "score": 90.0,
                "passed": True,
                "metrics": {"latency_ms": 100, "cost_usd": 0.02},
                "critical_failures": 0,
                "warning_count": 0,
            },
            {
                "pair_key": "case-1:1",
                "side": "baseline",
                "status": "completed",
                "score": 80.0,
                "passed": True,
                "metrics": {"latency_ms": 120, "cost_usd": 0.01},
                "critical_failures": 0,
                "warning_count": 0,
            },
        ],
        {"minimum_score": 70, "minimum_pass_rate": 80},
    )

    assert result["comparison"]["paired_n"] == 1
    assert result["comparison"]["score_delta"]["mean"] == 10.0
    assert result["comparison"]["candidate_wins"] == 1
    assert result["comparison"]["baseline_wins"] == 0


def test_critical_failure_marks_qualification_as_not_qualified() -> None:
    result = aggregate_evaluation(
        [
            {
                "pair_key": "case-1:1",
                "side": "candidate",
                "status": "completed",
                "score": 99.0,
                "passed": False,
                "metrics": {},
                "critical_failures": 1,
                "warning_count": 0,
            }
        ],
        {"minimum_score": 70, "minimum_pass_rate": 80},
    )

    assert result["qualification_status"] == "not_qualified"
    assert result["critical_failures"] == 1


def test_estimator_separates_scenarios_and_declares_confidence() -> None:
    estimate = build_estimate(
        values=[
            {"metrics": {"cost_usd": 0.01, "latency_ms": 100, "agent_run_count": 2}},
            {"metrics": {"cost_usd": 0.02, "latency_ms": 200, "agent_run_count": 3}},
            {"metrics": {"cost_usd": 0.03, "latency_ms": 300, "agent_run_count": 4}},
            {"metrics": {"cost_usd": 0.02, "latency_ms": 180, "agent_run_count": 3}},
            {"metrics": {"cost_usd": 0.015, "latency_ms": 150, "agent_run_count": 2}},
        ],
        volume=10_000,
        target_type="network",
    )

    assert estimate["confidence"] == "medium"
    assert estimate["scenarios"]["optimistic"]["provider_cost_usd"] is not None
    assert estimate["scenarios"]["expected"]["provider_cost_usd"] is not None
    assert estimate["scenarios"]["conservative"]["provider_cost_usd"] is not None
    assert estimate["scenarios"]["expected"]["agent_runs"] > 10_000
