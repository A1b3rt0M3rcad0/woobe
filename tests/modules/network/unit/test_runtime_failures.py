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
        trace_id=invocation_id,
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
        "trace_id": str(invocation_id),
    }


def test_classifies_the_original_provider_connection_error_through_wrappers() -> None:
    try:
        try:
            raise ConnectionError("Connection refused by private provider host")
        except ConnectionError as provider_error:
            raise RuntimeError("instrumented execution failed") from provider_error
    except RuntimeError as instrumented_error:
        try:
            raise ValueError("AI provider error: request failed") from instrumented_error
        except ValueError as wrapped:
            failure = classify_runtime_exception(wrapped)

    assert failure.code == "provider_unreachable"
    assert failure.stage == "provider_request"
    assert failure.retryable is True
    assert "private provider host" not in failure.public_payload()["message"]
    assert "private provider host" in failure.internal_detail


def test_classifies_a_generic_provider_rejection_without_leaking_detail() -> None:
    failure = classify_runtime_exception(
        ValueError("AI provider error: upstream rejected proprietary payload")
    )

    assert failure.code == "provider_request_error"
    assert failure.stage == "provider_request"
    assert failure.retryable is False
    assert failure.public_payload()["message"] == (
        "The model provider rejected the Agent request."
    )
    assert "proprietary payload" not in failure.public_payload()["message"]


def test_classifies_missing_worker_http_runtime_as_bootstrap_error() -> None:
    failure = classify_runtime_exception(
        RuntimeError("HTTP tool executor is not configured")
    )

    assert failure.code == "runtime_configuration_error"
    assert failure.stage == "agent_bootstrap"
    assert failure.retryable is False
