from __future__ import annotations

from modules.evaluation.infra.workers.resumable_authoring_worker import (
    _provider_action_failure,
)


def test_insufficient_balance_pauses_authoring() -> None:
    failure = _provider_action_failure(
        "HTTP 402: insufficient balance for this provider account"
    )

    assert failure == {
        "category": "provider_insufficient_balance",
        "retryable": False,
        "recommended_action": "restore_balance_or_change_model",
        "pausable": True,
    }


def test_quota_exhausted_pauses_authoring() -> None:
    failure = _provider_action_failure(
        "insufficient_quota: quota exhausted; update billing"
    )

    assert failure is not None
    assert failure["category"] == "provider_insufficient_balance"
    assert failure["pausable"] is True


def test_rate_limit_is_not_misclassified_as_balance() -> None:
    assert _provider_action_failure("HTTP 429 rate limit exceeded") is None


def test_invalid_credential_pauses_for_model_or_credential_change() -> None:
    failure = _provider_action_failure("HTTP 401 unauthorized credential")

    assert failure is not None
    assert failure["category"] == "credential_error"
    assert failure["recommended_action"] == "change_model_or_credential"
