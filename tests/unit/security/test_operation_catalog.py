from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from pydantic import ValidationError

from woobe_api.security.operation_catalog import operation_catalog, resolve_operation
from woobe_api.http.shared.preconditions import expected_revision
from woobe_api.http.identity.authority_routes import CategoryUpdateRequest
from woobe_api.http.core.control_key_routes import UpdateControlKeyRequest


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/ai/agents/future-resource/hidden"),
        ("POST", "/core/workspaces/test/control-keys/future-mutation"),
        ("PATCH", "/network/future-operation"),
        ("POST", "/v1/run"),
        ("GET", "/identity/workspaces/anything/members"),
    ],
)
def test_unknown_or_non_control_operations_are_closed(method, path):
    assert resolve_operation(method, path)[0] is None


@pytest.mark.parametrize(
    "path,body,permission",
    [
        (
            f"/network/{uuid4()}/promotions",
            {"environment": "production"},
            "network:production",
        ),
        (
            f"/network/{uuid4()}/promotions",
            {"environment": "staging"},
            "network:version",
        ),
        (
            f"/ai/agents/{uuid4()}/runtime-environments/production",
            {},
            "agent:production",
        ),
        ("/knowledge/search", {}, "knowledge:read"),
        ("/tools/secrets", {}, "secret:write"),
    ],
)
def test_operation_effect_and_environment_choose_exact_permission(
    path, body, permission
):
    method = "PATCH" if "runtime-environments" in path else "POST"
    assert resolve_operation(method, path, body)[0] == permission


def test_new_route_is_advertised_as_unsupported_until_reviewed():
    app = FastAPI()

    @app.get("/ai/agents/{agent_id}/future")
    def future():
        pass

    operation = operation_catalog(app.routes)["operations"][0]
    assert not operation["control_key_supported"]
    assert operation["permission"] is None


@pytest.mark.parametrize("suffix", ["promotions", "promotions/preview"])
@pytest.mark.parametrize("environment,permission", [
    ("staging", "network:version"), ("production", "network:production"),
])
def test_network_preview_and_publication_require_the_same_environment_authority(suffix, environment, permission):
    assert resolve_operation("POST", f"/network/{uuid4()}/{suffix}",
        {"environment": environment})[0] == permission


def test_network_preview_catalog_advertises_production_permission_variant():
    from woobe_api.http.network.runtime_routes import router
    app = FastAPI()
    app.include_router(router)
    preview = next(item for item in operation_catalog(app.routes)["operations"]
        if item["path"].endswith("/promotions/preview"))
    assert preview["permission_variants"]["environment=production"] == "network:production"


@pytest.mark.parametrize(
    "header,status",
    [
        (None, 428),
        ("*", 412),
        ('W/"category:wrong:1"', 412),
        ('"category:wrong:1"', 412),
    ],
)
def test_mutation_requires_strong_resource_etag(header, status):
    headers = [] if header is None else [(b"if-match", header.encode())]
    request = Request({"type": "http", "headers": headers})
    with pytest.raises(HTTPException) as exc:
        expected_revision(request, kind="category", resource_id=uuid4())
    assert exc.value.status_code == status


def test_etag_captures_exact_revision():
    category_id = uuid4()
    request = Request(
        {
            "type": "http",
            "headers": [(b"if-match", f'"category:{category_id}:7"'.encode())],
        }
    )
    assert expected_revision(request, kind="category", resource_id=category_id) == 7


@pytest.mark.parametrize("revision", ["9" * 5000, "2147483648", "0", "01"])
def test_etag_rejects_out_of_range_revision_without_server_error(revision):
    category_id = uuid4()
    request = Request({"type": "http", "headers": [
        (b"if-match", f'"category:{category_id}:{revision}"'.encode())
    ]})
    with pytest.raises(HTTPException) as exc:
        expected_revision(request, kind="category", resource_id=category_id)
    assert exc.value.status_code == 412


@pytest.mark.parametrize(
    "model,field",
    [
        (CategoryUpdateRequest, "name"),
        (CategoryUpdateRequest, "permissions"),
        (CategoryUpdateRequest, "conditions"),
        (UpdateControlKeyRequest, "permissions"),
        (UpdateControlKeyRequest, "project_grants"),
        (UpdateControlKeyRequest, "on_project_create_permissions"),
    ],
)
def test_null_cannot_clear_non_nullable_authority_fields(model, field):
    with pytest.raises(ValidationError):
        model.model_validate({field: None})
    assert model.model_validate({}).model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize("method,permission", [("GET", "run:read"), ("POST", None)])
def test_agent_session_listing_is_an_explicit_read_operation(method, permission):
    assert resolve_operation(method, f"/runtime/agents/{uuid4()}/sessions")[0] == permission
    assert resolve_operation(method, f"/runtime/agents/{uuid4()}/sessions/hidden")[0] is None
