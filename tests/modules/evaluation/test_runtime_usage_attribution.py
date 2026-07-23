from uuid import uuid4

from modules.agent.application.use_cases.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.messaging.event_mappers import (
    _active_runtime_context_payload,
)


def test_runtime_context_defaults_to_operational_purpose() -> None:
    context = new_execution_context()

    assert context.run_purpose == "operational"
    assert context.evaluation_run_id is None
    assert context.target_snapshot_hash is None


def test_evaluation_context_propagates_snapshot_identity() -> None:
    context = new_execution_context()
    context.run_purpose = "evaluation"
    context.evaluation_run_id = uuid4()
    context.evaluation_trial_id = uuid4()
    context.evaluation_target_id = uuid4()
    context.target_snapshot_hash = "a" * 64
    context.target_snapshot_label = "production"
    context.evaluation_role = "target"

    token = current_execution.set(context)
    try:
        payload = _active_runtime_context_payload()
    finally:
        current_execution.reset(token)

    assert payload["run_purpose"] == "evaluation"
    assert payload["evaluation_run_id"] == str(context.evaluation_run_id)
    assert payload["evaluation_trial_id"] == str(context.evaluation_trial_id)
    assert payload["evaluation_target_id"] == str(context.evaluation_target_id)
    assert payload["target_snapshot_hash"] == "a" * 64
    assert payload["target_snapshot_label"] == "production"
    assert payload["evaluation_role"] == "target"
