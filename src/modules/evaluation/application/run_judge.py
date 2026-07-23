from __future__ import annotations

from typing import Any
from uuid import UUID


_GOVERNANCE_KEYS = {
    "judge_model_snapshot",
    "judge_model_snapshot_hash",
    "judge_protocol_version",
}


def clean_suite_judge_config(value: dict[str, Any] | None) -> dict[str, Any]:
    """Return the reusable Judge policy without a stale Suite-bound model snapshot."""

    source = dict(value or {})
    for key in _GOVERNANCE_KEYS:
        source.pop(key, None)
    return source


def run_judge_protocol(run: Any) -> dict[str, Any]:
    policy = getattr(run, "execution_policy", None)
    policy = policy if isinstance(policy, dict) else {}
    value = policy.get("judge_protocol")
    return dict(value) if isinstance(value, dict) else {}


def selected_judge_provider_model_id(run: Any, fallback: UUID) -> UUID:
    protocol = run_judge_protocol(run)
    value = protocol.get("judge_provider_model_id")
    if value:
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            pass
    return fallback


def selected_judge_config(
    run: Any,
    fallback: dict[str, Any] | None,
) -> dict[str, Any]:
    protocol = run_judge_protocol(run)
    value = protocol.get("normalized_judge_config")
    selected = (
        dict(value)
        if isinstance(value, dict)
        else clean_suite_judge_config(fallback)
    )
    snapshot = protocol.get("judge_model_snapshot")
    if isinstance(snapshot, dict):
        selected["judge_model_snapshot"] = dict(snapshot)
        selected["judge_model_snapshot_hash"] = protocol.get(
            "judge_model_snapshot_hash"
        )
        selected["judge_protocol_version"] = "frozen-judge-runtime-v1"
    return selected


def judge_summary_from_run(run: Any) -> dict[str, Any] | None:
    protocol = run_judge_protocol(run)
    snapshot = protocol.get("judge_model_snapshot")
    snapshot = dict(snapshot) if isinstance(snapshot, dict) else {}

    aggregate = getattr(run, "aggregate_result", None)
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    preflight = aggregate.get("judge_preflight")
    preflight = preflight if isinstance(preflight, dict) else {}
    preflight_model = preflight.get("judge_model")
    preflight_model = dict(preflight_model) if isinstance(preflight_model, dict) else {}

    source = snapshot or preflight_model
    provider_model_id = (
        protocol.get("judge_provider_model_id")
        or source.get("provider_model_id")
    )
    if not provider_model_id:
        return None

    capabilities = source.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    return {
        "provider_model_id": str(provider_model_id),
        "display_name": source.get("display_name") or source.get("model") or str(provider_model_id),
        "provider": source.get("provider"),
        "model": source.get("model"),
        "credential_name": source.get("credential_name"),
        "response_strategy": capabilities.get("response_strategy"),
        "snapshot_hash": (
            protocol.get("judge_model_snapshot_hash")
            or source.get("snapshot_hash")
        ),
        "source": protocol.get("source") or "suite_default",
    }


__all__ = [
    "clean_suite_judge_config",
    "judge_summary_from_run",
    "run_judge_protocol",
    "selected_judge_config",
    "selected_judge_provider_model_id",
]
