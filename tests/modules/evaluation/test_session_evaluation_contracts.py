from __future__ import annotations

import pytest

from modules.evaluation.application.evaluation_kpis import (
    calculate_comparison_winner,
    canonical_evaluation_kpis,
)
from modules.evaluation.domain.contracts import normalize_test_case, validate_suite_draft
from shared.infra.errors import ValidationError


def _session_case() -> dict:
    return {
        "name": "Remember customer context",
        "case_type": "success",
        "interaction_mode": "session",
        "turns": [
            {
                "message": "My name is Alberto.",
                "expected_behavior": ["Acknowledge the provided name."],
            },
            {
                "message": "What name did I give you?",
                "expected_behavior": ["Recall Alberto."],
                "forbidden_behavior": ["Do not invent another name."],
            },
        ],
        "expected_contract": {
            "semantic_criteria": ["Maintain conversational context across turns."],
        },
        "production_frequency": 0.25,
    }


def test_session_case_normalizes_turns_into_runtime_payload() -> None:
    case = normalize_test_case(_session_case(), position=1)

    assert case["interaction_mode"] == "session"
    assert case["message"] == "My name is Alberto."
    assert case["input_payload"]["interaction_mode"] == "session"
    assert len(case["turns"]) == 2
    assert case["turns"][1]["position"] == 2
    assert case["turns"][1]["input_payload"]["message"] == "What name did I give you?"
    assert case["expected_contract"]["interaction_mode"] == "session"


def test_session_case_requires_at_least_two_turns() -> None:
    value = _session_case()
    value["turns"] = [{"message": "Only one turn"}]

    with pytest.raises(ValidationError, match="at least two turns"):
        normalize_test_case(value, position=1)


def test_suite_validation_reports_interaction_coverage() -> None:
    result = validate_suite_draft(
        {
            "cases": [
                _session_case(),
                {
                    "name": "Single question",
                    "case_type": "success",
                    "message": "What is the support email?",
                    "expected_contract": {
                        "semantic_criteria": ["Return the supported contact channel."]
                    },
                },
            ]
        }
    )

    assert result["valid"] is True
    assert result["interaction_coverage"] == {"single_turn": 1, "session": 1}


def test_canonical_kpis_include_session_operational_metrics() -> None:
    trials = [
        {
            "id": "trial-1",
            "test_case_id": "case-1",
            "pair_key": "case-1:1",
            "status": "completed",
            "score": 90,
            "passed": True,
            "metrics": {
                "interaction_mode": "session",
                "session_completed": True,
                "turn_count": 3,
                "completed_turn_count": 3,
                "cost_usd": 0.12,
                "latency_ms": 3000,
                "input_tokens": 900,
                "output_tokens": 300,
                "case_weight": 2,
                "production_frequency": 0.5,
            },
        },
        {
            "id": "trial-2",
            "test_case_id": "case-1",
            "pair_key": "case-1:2",
            "status": "completed",
            "score": 80,
            "passed": True,
            "metrics": {
                "interaction_mode": "session",
                "session_completed": True,
                "turn_count": 3,
                "completed_turn_count": 3,
                "cost_usd": 0.18,
                "latency_ms": 5000,
                "input_tokens": 1100,
                "output_tokens": 500,
                "case_weight": 2,
                "production_frequency": 0.5,
            },
        },
    ]

    kpis = canonical_evaluation_kpis(trials)

    assert kpis["quality_score"] == 85
    assert kpis["pass_rate"] == 100
    assert kpis["stable_case_count"] == 1
    assert kpis["session"]["session_count"] == 2
    assert kpis["session"]["session_completion_rate"] == 100
    assert kpis["session"]["average_turns_per_session"] == 3
    assert kpis["session"]["cost_usd_per_session"] == pytest.approx(0.15)
    assert kpis["session"]["cost_usd_per_turn"] == pytest.approx(0.05)


def test_comparison_winner_respects_maximize_and_minimize_directions() -> None:
    candidate = {
        "quality_score": 92,
        "pass_rate": 96,
        "runtime_cost_usd_per_trial": 0.05,
        "latency_median_ms": 900,
    }
    reference = {
        "quality_score": 87,
        "pass_rate": 90,
        "runtime_cost_usd_per_trial": 0.03,
        "latency_median_ms": 1200,
    }

    result = calculate_comparison_winner(
        candidate,
        reference,
        acceptance_policy=None,
        authoritative=True,
    )

    assert result["side"] == "candidate"
    assert result["authoritative"] is True
    per_kpi = {item["key"]: item for item in result["kpis"]}
    assert per_kpi["quality_score"]["winner"] == "candidate"
    assert per_kpi["pass_rate"]["winner"] == "candidate"
    assert per_kpi["runtime_cost_usd_per_trial"]["winner"] == "reference"
    assert per_kpi["latency_median_ms"]["winner"] == "candidate"
