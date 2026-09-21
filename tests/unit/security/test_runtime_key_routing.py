from woobe_api.security.http_guard import (
    is_runtime_execution_request,
    is_runtime_path,
    public_runtime_interface,
)


def test_public_runtime_interfaces_are_explicit() -> None:
    assert public_runtime_interface("POST", "/v1/run") == "http"
    assert public_runtime_interface("POST", "/v1/run/stream") == "stream"
    assert public_runtime_interface("POST", "/v1/output-context/validate") == "contract"
    assert public_runtime_interface("POST", "/v1/jobs") == "jobs"
    assert public_runtime_interface("GET", "/v1/jobs/123") == "jobs"
    assert public_runtime_interface("GET", "/v1/run") is None


def test_runtime_timeout_and_concurrency_skip_job_polling() -> None:
    assert is_runtime_path("/v1/jobs/123") is True
    assert is_runtime_execution_request("POST", "/v1/jobs") is True
    assert is_runtime_execution_request("GET", "/v1/jobs/123") is False
    assert is_runtime_path("/v1/output-context/validate") is True
    assert is_runtime_execution_request("POST", "/v1/output-context/validate") is False

