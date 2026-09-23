from uuid import uuid4

from starlette.requests import Request

from shared.security.tenancy import TenantAuthorizer
from woobe_api.security.http_guard import HttpSecurityGuard


def test_access_project_id_is_treated_as_project_context() -> None:
    project_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"access_project_id": project_id},
        {},
        {},
    )

    assert identifiers == [("access_project_id", project_id)]


def test_network_id_is_visible_to_tenant_authorization() -> None:
    network_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"network_id": network_id},
        {},
        {},
    )

    assert identifiers == [("network_id", network_id)]


def test_run_id_is_visible_to_tenant_authorization() -> None:
    run_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"run_id": run_id},
        {},
        {},
    )

    assert identifiers == [("run_id", run_id)]


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("test", 80),
        }
    )


def test_run_trace_authorization_uses_run_specific_identifier() -> None:
    trace_id = uuid4()

    result = HttpSecurityGuard._authorization_path_params(
        _request(f"/runtime/runs/by-trace/{trace_id}"),
        {"trace_id": str(trace_id)},
    )

    assert result == {"run_trace_id": str(trace_id)}


def test_observability_trace_authorization_keeps_observability_identifier() -> None:
    trace_id = uuid4()

    result = HttpSecurityGuard._authorization_path_params(
        _request(f"/observability/traces/{trace_id}"),
        {"trace_id": str(trace_id)},
    )

    assert result == {"trace_id": str(trace_id)}
