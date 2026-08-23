from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.network.application.runtime_failures import classify_runtime_exception


def test_provider_failure_exposes_safe_phase_and_partial_result() -> None:
    failure = classify_runtime_exception(
        InstrumentedExecutionError(
            "status code: 400",
            failure_context={
                "phase": "final_response_generation",
                "call_index": 6,
                "upstream_status": 400,
                "upstream_error_code": "invalid_request",
                "partial_result_available": True,
            },
        )
    )

    assert failure.code == "provider_request_error"
    assert failure.safe_message == "The model provider rejected the final response request."
    assert failure.phase == "final_response_generation"
    assert failure.call_index == 6
    assert failure.upstream_status == 400
    assert failure.upstream_error_code == "invalid_request"
    assert failure.partial_result_available is True

    payload = failure.public_payload()
    assert payload["partial_result_available"] is True
    assert payload["phase"] == "final_response_generation"
