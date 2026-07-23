from __future__ import annotations

from modules.evaluation.application.hardened_service import (
    HardenedEvaluationApplicationService,
)


def test_ready_live_affordability_replaces_unknown_warning() -> None:
    merged = HardenedEvaluationApplicationService._merge_affordability(
        {
            "status": "ready",
            "can_execute": True,
            "blockers": [],
            "warnings": [
                {
                    "code": "judge_affordability_unknown",
                    "message": "metadata did not expose balance",
                },
                {
                    "code": "judge_pricing_unknown",
                    "message": "pricing warning",
                },
            ],
        },
        {
            "status": "ready",
            "source": "openrouter_api_v1_key",
            "blockers": [],
            "warnings": [],
            "limit_remaining_usd": 12.5,
        },
    )

    assert merged["can_execute"] is True
    assert merged["credential_remaining_usd"] == 12.5
    assert [item["code"] for item in merged["warnings"]] == [
        "judge_pricing_unknown"
    ]


def test_live_credit_blocker_prevents_evaluation() -> None:
    merged = HardenedEvaluationApplicationService._merge_affordability(
        {
            "status": "ready",
            "can_execute": True,
            "blockers": [],
            "warnings": [],
        },
        {
            "status": "blocked",
            "source": "openrouter_api_v1_key",
            "blockers": [
                {
                    "code": "judge_insufficient_credits",
                    "message": "remaining balance is below maximum Judge cost",
                }
            ],
            "warnings": [],
            "limit_remaining_usd": 0.0,
        },
    )

    assert merged["status"] == "blocked"
    assert merged["can_execute"] is False
    assert merged["blockers"][0]["code"] == "judge_insufficient_credits"
