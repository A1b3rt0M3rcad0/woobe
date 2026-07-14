from uuid import uuid4

from modules.network.application.runtime_failures import (
    NetworkRuntimeFailure,
    classify_runtime_exception,
)


def test_classifies_settings_bootstrap_without_exposing_internal_detail() -> None:
    failure = classify_runtime_exception(
        RuntimeError("Settings ValidationError: secret_key is required")
    )

    assert failure.code == "credential_error"
    assert failure.stage == "credential_resolution"
    assert "secret_key" not in failure.public_payload()["message"]


def test_failure_payload_carries_the_causal_agent_run() -> None:
    invocation_id = uuid4()
    node_id = uuid4()
    agent_id = uuid4()
    failure = NetworkRuntimeFailure(
        code="provider_timeout",
        stage="provider_request",
        safe_message="The model provider did not answer before the timeout.",
        internal_detail="private upstream detail",
        retryable=True,
    ).with_run_context(
        invocation_id=invocation_id,
        node_id=node_id,
        agent_id=agent_id,
    )

    assert str(failure) == "private upstream detail"
    assert failure.public_payload() == {
        "code": "provider_timeout",
        "stage": "provider_request",
        "message": "The model provider did not answer before the timeout.",
        "retryable": True,
        "cause_invocation_id": str(invocation_id),
        "cause_node_id": str(node_id),
        "cause_agent_id": str(agent_id),
    }
