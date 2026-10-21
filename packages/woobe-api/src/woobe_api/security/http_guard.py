from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from hmac import compare_digest
from typing import Any
from uuid import UUID

from fastapi import Request

from shared.infra.config import Settings
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    PayloadTooLargeError,
)
from shared.security.api_keys import (
    API_KEY_SCOPE_RUNTIME_EXECUTE,
    API_KEY_SCOPE_TRACES_READ,
    API_KEY_SCOPE_USAGE_READ,
    is_api_key_candidate,
)
from shared.security.authentication import SecurityAuthenticator
from shared.security.principal import (
    ProjectApiPrincipal,
    SecurityPrincipal,
)
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    LoginRateLimiter,
)
from woobe_api.security.operation_catalog import resolve_operation, verified_query_context, configuration_query_scope

PUBLIC_PATHS = {
    "/identity/auth/login",
    "/identity/auth/logout",
    "/identity/auth/register",
    "/identity/auth/refresh",
    "/identity/instance/status",
    "/identity/instance/bootstrap",
}
_LOCAL_ENVIRONMENTS = {"development", "dev", "test", "local"}
_ALLOWED_SAME_SITE = {"lax", "strict", "none"}
_CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def is_artifacts_runtime_path(path: str) -> bool:
    return re.fullmatch(
        r'/v1/(?:artifact-workspaces(?:/[A-Za-z0-9_-]+(?:/(?:artifacts(?:/[A-Za-z0-9_-]+(?:/(?:content|revisions(?:/[A-Za-z0-9_-]+/document-index)?))?)?|uploads(?:/[A-Za-z0-9_-]+(?:/(?:parts|finalize))?)?|search|processing-profile))?)?'
        r'|artifacts/[A-Za-z0-9_-]+/(?:revisions/[A-Za-z0-9_-]+(?:/content|/representations(?:/[A-Za-z0-9_-]+(?:/entries(?:/[A-Za-z0-9_-]+/(?:content|copy))?|/pages/[0-9]+/image)?)?)?|processing(?:/[A-Za-z0-9_-]+(?:/cancel)?)?|representations(?:/[A-Za-z0-9_-]+)?)'
        r'|document-indexes/[A-Za-z0-9_-]+(?:/nodes(?:/[A-Za-z0-9_-]+(?:/content)?)?)?'
        r'|source-references/resolve|artifact-sources/(?:read|resolve)|artifact-capabilities|artifact-processing-capabilities'
        r'|artifact-processing-profiles(?:/[A-Za-z0-9_-]+/revisions/[0-9]+)?)', path,
    ) is not None


def _configuration_permissions(method, path, body, path_params):
    """Additional authority; never infer it from a client-supplied marker."""
    if not isinstance(body, dict):
        return []
    credential = path_params.get("credential_id")
    provider_write = (method == "POST" and path == "/ai/credentials") or (
        method == "PATCH" and credential is not None and path == f"/ai/credentials/{credential}")
    provider_rotate = method == "POST" and credential is not None and path == f"/ai/credentials/{credential}/rotate"
    permissions = []
    if method == 'POST' and path in {
        '/tools/mcp/oauth/start', '/tools/mcp/oauth/complete',
        '/tools/mcp/oauth/device/start', '/tools/mcp/oauth/device/poll',
    }:
        permissions.append(('project:environment:value:write', 'tool:write'))
    if method in {'POST', 'PUT', 'PATCH'} and '/tools' in path:
        from shared.contracts.project_configuration import tool_configuration_permissions
        permissions.extend(tool_configuration_permissions(body.get('config'),
            compatibility_update=method == 'PATCH' and path_params.get('tool_id') is not None))
    if provider_write and "authentication" in body:
        permissions.append(("project:environment:bind", None))
    if (provider_write or provider_rotate) and "secret" in body:
        permissions.append(("project:environment:value:write", "provider:credential:rotate" if provider_rotate else "provider:write"))
    return permissions


def _is_public_run_cancel(method: str, path: str) -> bool:
    return (
        method.upper() == "POST"
        and path.startswith("/v1/runs/")
        and path.endswith("/cancel")
    )


def public_runtime_interface(method: str, path: str) -> str | None:
    normalized_method = method.upper()
    if normalized_method in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'} and is_artifacts_runtime_path(path):
        return 'artifacts'
    if normalized_method == "POST" and path == "/v1/run":
        return "http"
    if normalized_method == "POST" and path == "/v1/run/stream":
        return "stream"
    if normalized_method == "POST" and path == "/v1/contracts/validate":
        return "contract"
    if (
        normalized_method == "GET"
        and path.startswith("/v1/runs/")
        and path.endswith("/stream")
    ):
        return "stream"
    if _is_public_run_cancel(normalized_method, path):
        return "http"
    if (
        normalized_method == "GET"
        and path.startswith("/v1/sessions/")
        and path.endswith("/active-run")
    ):
        return "stream"
    if normalized_method == "POST" and path == "/v1/jobs":
        return "jobs"
    if normalized_method == "GET" and path.startswith("/v1/jobs/"):
        return "jobs"
    return None


def is_runtime_path(path: str) -> bool:
    return (
        is_artifacts_runtime_path(path)
        or path.startswith("/runtime/")
        or path.startswith("/agent/runtime/")
        or path == "/v1/run"
        or path == "/v1/run/stream"
        or path == "/v1/contracts/validate"
        or path == "/v1/jobs"
        or path.startswith("/v1/jobs/")
        or (
            path.startswith("/v1/runs/")
            and (path.endswith("/stream") or path.endswith("/cancel"))
        )
        or (
            path.startswith("/v1/sessions/")
            and path.endswith("/active-run")
        )
    )


def is_chat_surface_public_path(path: str) -> bool:
    return path.startswith("/v1/chat-surfaces/") or path.startswith("/v1/chat/")


def is_runtime_execution_request(method: str, path: str) -> bool:
    if path.startswith("/runtime/") or path.startswith("/agent/runtime/"):
        return True
    if _is_public_run_cancel(method, path):
        return False
    interface = public_runtime_interface(method, path)
    if method.upper() == "GET" and interface == "stream":
        return False
    return interface in {"http", "stream"} or (
        interface == "jobs" and method.upper() == "POST"
    )


def _validate_runtime_security_settings(settings: Settings) -> None:
    environment = settings.environment.strip().lower()
    cookie_settings = (
        (
            "access",
            bool(settings.access_cookie_secure),
            settings.access_cookie_same_site,
        ),
        (
            "refresh",
            bool(settings.refresh_cookie_secure),
            settings.refresh_cookie_same_site,
        ),
    )

    for name, secure, same_site_value in cookie_settings:
        same_site = str(same_site_value).strip().lower()
        if same_site not in _ALLOWED_SAME_SITE:
            raise ValueError(f"Invalid {name} cookie same-site policy")
        if environment not in _LOCAL_ENVIRONMENTS and not secure:
            raise ValueError(f"Production {name} cookies require transport security")
        if same_site == "none" and not secure:
            raise ValueError(f"Cross-site {name} cookies require transport security")


def _required_api_key_scope(method: str, path: str) -> str | None:
    if is_runtime_path(path):
        return API_KEY_SCOPE_RUNTIME_EXECUTE
    if method == "GET" and path.startswith("/observability/traces"):
        return API_KEY_SCOPE_TRACES_READ
    if method == "GET" and path.startswith("/metering/"):
        return API_KEY_SCOPE_USAGE_READ
    return None


def _values_for_key(value: Any, target: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) == target:
                found.append(item)
            if isinstance(item, (Mapping, list, tuple)):
                found.extend(_values_for_key(item, target))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_values_for_key(item, target))
    return found


def _serialized_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), default=str).encode("utf-8"))


class HttpSecurityGuard:
    def __init__(
        self,
        *,
        authenticator: SecurityAuthenticator,
        login_rate_limiter: LoginRateLimiter,
        api_key_concurrency_limiter: ApiKeyConcurrencyLimiter,
        settings: Settings,
    ) -> None:
        _validate_runtime_security_settings(settings)
        self._authenticator = authenticator
        self._login_rate_limiter = login_rate_limiter
        self._api_key_concurrency_limiter = api_key_concurrency_limiter
        self._settings = settings

    @property
    def runtime_timeout_seconds(self) -> float:
        return self._settings.runtime_total_timeout_seconds

    def requires_runtime_permit(
        self,
        request: Request,
        principal: SecurityPrincipal | None,
    ) -> bool:
        return isinstance(
            principal, ProjectApiPrincipal
        ) and is_runtime_execution_request(request.method, request.url.path)

    async def acquire_runtime_permit(self, principal: ProjectApiPrincipal) -> UUID:
        return await self._api_key_concurrency_limiter.acquire(
            str(principal.api_key_id)
        )

    async def release_runtime_permit(self, lease_id: UUID) -> None:
        await self._api_key_concurrency_limiter.release(lease_id)

    async def authenticate_and_authorize(
        self,
        request: Request,
        *,
        body: Any,
        query_params: dict[str, Any],
        path_params: dict[str, Any],
    ) -> SecurityPrincipal | None:
        if request.method == "OPTIONS":
            return None

        path = request.url.path
        if path == "/identity/auth/login":
            client = request.client.host if request.client else "unknown"
            await self._login_rate_limiter.consume(client)

        if path in PUBLIC_PATHS or is_chat_surface_public_path(path):
            return None

        if is_runtime_path(path):
            self._validate_runtime_payload(request, body)

        authorization_path_params = self._authorization_path_params(
            request,
            path_params,
            body,
        )

        query_params = configuration_query_scope(request.method, path, path_params, query_params)
        authorization_path_params = verified_query_context(
            request.method, path, authorization_path_params, query_params
        )
        body = self._authorization_body(request, path_params, body)
        configuration_permissions = _configuration_permissions(request.method, path, body, path_params)
        authorization = request.headers.get("authorization", "")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer" and credentials:
            if is_api_key_candidate(credentials):
                principal = await self._authenticate_api_key(
                    request=request,
                    credentials=credentials,
                    body=body,
                    query_params=query_params,
                    path_params=authorization_path_params,
                )
                for permission, legacy in configuration_permissions:
                    from shared.contracts.project_configuration import configuration_permission_contexts
                    for context in configuration_permission_contexts(permission, legacy, authorization_path_params):
                        await self._authenticator.authenticate_api_key(credentials=credentials,
                            required_scope=_required_api_key_scope(request.method, request.url.path),
                            runtime_interface=public_runtime_interface(request.method, request.url.path),
                            path_params=context, query_params=query_params, body=body, control_permission=permission)
                return principal
            access_token = credentials
            token_source = "header"
        else:
            access_token = request.cookies.get(self._settings.access_cookie_name)
            token_source = "cookie"

        if not access_token:
            raise AuthenticationError("Authentication required")

        principal = await self._authenticator.authenticate_user(
            access_token=access_token,
            path_params=authorization_path_params,
            query_params=query_params,
            body=body,
            required_permission=resolve_operation(request.method, path, body)[0],
            mutation=request.method.upper() in _CSRF_METHODS,
        )

        if token_source == "cookie":
            self._validate_csrf(request)

        for permission, legacy in configuration_permissions:
            from shared.contracts.project_configuration import configuration_permission_contexts
            for context in configuration_permission_contexts(permission, legacy, authorization_path_params):
                await self._authenticator.authenticate_user(access_token=access_token,
                    path_params=context, query_params=query_params, body=body,
                    required_permission=permission, mutation=True)

        return principal

    @staticmethod
    def _authorization_path_params(
        request: Request,
        path_params: dict[str, Any],
        body: Any = None,
    ) -> dict[str, Any]:
        project = path_params.get("project_id")
        if project and request.method == "POST" and isinstance(body, dict):
            base = f"/core/projects/{project}/configuration/"
            environments = []
            if request.url.path == base + "use-policies" or (
                path_params.get("alias_id") and request.url.path == base + f"legacy-bindings/{path_params['alias_id']}/convert"):
                environments = body.get("environments")
            elif request.url.path == base + "value-batches":
                operations = body.get("operations")
                if isinstance(operations, list):
                    environments = [op.get("environment") for op in operations if isinstance(op, dict)]
            # This is only the preliminary boundary check. The authoritative
            # configuration transaction authorizes every requested environment.
            if isinstance(environments, list) and environments and environments[0] in ("draft", "staging", "production"):
                return {**path_params, "environment": environments[0]}
        if request.method == "GET" and "project_id" in path_params and "resource_id" in path_params:
            project, resource = path_params["project_id"], path_params["resource_id"]
            for plural, identifier in (("agents", "agent_id"), ("networks", "network_id")):
                base = f"/projects/{project}/{plural}/{resource}/asac/"
                if request.url.path in {base + "current", base + "history"}:
                    normalized = dict(path_params)
                    normalized[identifier] = normalized.pop("resource_id")
                    normalized["environment"] = (request.query_params.get("environment") or "production") if request.url.path == base + "current" else "production"
                    return normalized
        if "project_id" in path_params and "resource_id" in path_params:
            # Normalize only the reviewed Draft transport's exact shapes. Client
            # query parameters cannot turn Draft writes into Production grants.
            for plural, identifier in (("agents", "agent_id"), ("networks", "network_id")):
                base = f"/projects/{path_params['project_id']}/{plural}/{path_params['resource_id']}/asac/"
                category = path_params.get("category")
                receipt_id = path_params.get("receipt_id")
                if request.method == "GET" and category in {"revision", "evaluation", "publication", "deployment"} and receipt_id and request.url.path == base + f"signed-receipts/{category}/{receipt_id}":
                    normalized = dict(path_params)
                    normalized[identifier] = normalized.pop("resource_id")
                    normalized["environment"] = ((request.query_params.get("environment") or "production")
                        if category == "deployment" else "draft" if category == "revision" else "staging")
                    return normalized
                git_route=(request.method=='POST' and request.url.path==base+'git-attestations') or (request.method=='GET' and 'attestation_id' in path_params and request.url.path==base+'git-attestations/'+str(path_params['attestation_id']))
                if git_route:
                    normalized=dict(path_params)
                    normalized[identifier]=normalized.pop('resource_id')
                    normalized['environment']='staging'
                    return normalized
                deployment_route=(request.method=="POST" and request.url.path in {base+"deployment-plans",base+"deployments"}) or (request.method=="GET" and (("plan_id" in path_params and request.url.path==base+"deployment-plans/"+str(path_params["plan_id"])) or ("deployment_id" in path_params and request.url.path==base+"deployments/"+str(path_params["deployment_id"]))))
                if deployment_route:
                    data=body if isinstance(body,dict) else {}
                    normalized=dict(path_params)
                    normalized[identifier]=normalized.pop("resource_id")
                    normalized["environment"]=(request.query_params.get("environment") or "production") if request.method=="GET" else data.get("environment","production")
                    return normalized
                lease_route=(request.method=="GET" and request.url.path==base+"leases") or (request.method=="POST" and request.url.path in {base+"leases/"+action for action in ("acquire","renew","release","break")})
                if lease_route:
                    data=body if isinstance(body,dict) else {}
                    scope=(request.query_params.get("scope") or "resource") if request.method=="GET" else data.get("scope")
                    normalized=dict(path_params)
                    normalized[identifier]=normalized.pop("resource_id")
                    normalized["environment"]=scope if scope in {"staging","production"} else "draft"
                    return normalized
                candidate_route = (request.method == "POST" and request.url.path == base + "candidates") or (
                    request.method == "GET" and "candidate_id" in path_params
                    and request.url.path == base + "candidates/" + str(path_params["candidate_id"]))
                if "candidate_id" in path_params and request.method == "POST" and request.url.path == base + "candidates/" + str(path_params["candidate_id"]) + "/evaluations":
                    candidate_route = True
                if "evaluation_id" in path_params and (request.method, request.url.path) in {
                    ("GET", base + "evaluations/" + str(path_params["evaluation_id"])),
                    ("POST", base + "evaluations/" + str(path_params["evaluation_id"]) + "/reconcile")}:
                    candidate_route = True
                if ((request.method == "POST" and request.url.path == base + "publications") or
                    (request.method == "GET" and "publication_id" in path_params and request.url.path == base + "publications/" + str(path_params["publication_id"])) or
                    (plural == "networks" and request.method == "POST" and "publication_id" in path_params and request.url.path in {base + "publications/" + str(path_params["publication_id"]) + suffix for suffix in ("/reconcile", "/cancel")})):
                    candidate_route = True
                if candidate_route:
                    normalized = dict(path_params)
                    normalized[identifier] = normalized.pop("resource_id")
                    normalized["environment"] = "staging"
                    return normalized
                if request.method=='POST' and 'draft_id' in path_params and request.url.path==base+'drafts/'+str(path_params['draft_id'])+'/stage':
                    normalized=dict(path_params)
                    normalized[identifier]=normalized.pop('resource_id')
                    normalized['environment']='staging'
                    return normalized
                if request.method == "GET" and "operation_id" in path_params and request.url.path == base + "operations/" + str(path_params["operation_id"]):
                    normalized = dict(path_params)
                    normalized[identifier] = normalized.pop("resource_id")
                    normalized["environment"] = request.query_params.get("environment") or "draft"
                    return normalized
                allowed = {("GET", "drafts"), ("GET", "drafts/preflight"), ("POST", "drafts"), ("POST", "revisions")}
                if 'draft_id' in path_params:
                    draft='drafts/'+str(path_params['draft_id'])
                    allowed.update({('GET',draft+'/editor'),('PUT',draft+'/editor'),('POST',draft+'/checkpoint')})
                for parameter, route, methods in (("draft_id", "drafts", ("GET", "PUT")),
                        ("revision_id", "revisions", ("GET",)), ("operation_id", "operations", ("GET",))):
                    if parameter in path_params:
                        allowed.update((method, f"{route}/{path_params[parameter]}") for method in methods)
                if request.url.path.startswith(base) and (request.method, request.url.path[len(base):]) in allowed:
                    normalized = dict(path_params)
                    normalized[identifier] = normalized.pop("resource_id")
                    normalized["environment"] = "draft"
                    return normalized
        if request.url.path.startswith("/core/projects/") and "resource_id" in path_params:
            normalized = dict(path_params)
            normalized["project_id"] = normalized.pop("resource_id")
            return normalized
        if (
            request.url.path.startswith("/runtime/runs/by-trace/")
            and "trace_id" in path_params
        ):
            normalized = dict(path_params)
            normalized["run_trace_id"] = normalized.pop("trace_id")
            return normalized
        if (
            request.method == "GET"
            and path_params.get("agent_id") is not None
            and request.url.path
            == f"/runtime/agents/{path_params['agent_id']}/sessions"
        ):
            # This reviewed collection handler filters by the same query value.
            # Grant conditions must authorize that environment before listing.
            environment = request.query_params.get("environment") or "draft"
            normalized = dict(path_params)
            normalized["environment"] = environment
            return normalized
        return path_params

    @staticmethod
    def _authorization_body(request: Request, path_params: dict, body: Any) -> Any:
        # The portable deployment vocabulary uses release_id for both owners.
        # Tenant references must resolve that UUID in its exact owning table.
        if (request.method == "POST" and "project_id" in path_params and "resource_id" in path_params
            and request.url.path == f"/projects/{path_params['project_id']}/networks/{path_params['resource_id']}/asac/deployment-plans"
            and isinstance(body, dict) and "release_id" in body):
            normalized = dict(body)
            normalized["network_version_id"] = normalized.pop("release_id")
            return normalized
        return body

    async def _authenticate_api_key(
        self,
        *,
        request: Request,
        credentials: str,
        body: Any,
        query_params: dict[str, Any],
        path_params: dict[str, Any],
    ) -> SecurityPrincipal:
        required_scope = _required_api_key_scope(request.method, request.url.path)
        return await self._authenticator.authenticate_api_key(
            credentials=credentials,
            required_scope=required_scope,
            runtime_interface=public_runtime_interface(
                request.method,
                request.url.path,
            ),
            path_params=path_params,
            query_params=query_params,
            body=body,
            control_permission=resolve_operation(
                request.method,
                request.url.path,
                body,
            )[0],
        )

    def _validate_csrf(self, request: Request) -> None:
        if request.method.upper() not in _CSRF_METHODS:
            return

        csrf_cookie = request.cookies.get(self._settings.csrf_cookie_name)
        csrf_header = request.headers.get(self._settings.csrf_header_name)
        if not csrf_cookie or not csrf_header:
            raise AuthorizationError("CSRF validation failed")
        if not compare_digest(csrf_cookie, csrf_header):
            raise AuthorizationError("CSRF validation failed")

    def _validate_runtime_payload(self, request: Request, body: Any) -> None:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self._settings.runtime_max_request_bytes:
                    raise PayloadTooLargeError("Runtime request body is too large")
            except ValueError:
                raise PayloadTooLargeError("Invalid Content-Length header") from None

        if body is None:
            return
        if _serialized_size(body) > self._settings.runtime_max_request_bytes:
            raise PayloadTooLargeError("Runtime request body is too large")

        for key in ("message", "prompt"):
            for value in _values_for_key(body, key):
                if (
                    isinstance(value, str)
                    and len(value) > self._settings.runtime_max_prompt_chars
                ):
                    raise PayloadTooLargeError("Runtime prompt is too large")

        for value in _values_for_key(body, "metadata"):
            if _serialized_size(value) > self._settings.runtime_max_metadata_bytes:
                raise PayloadTooLargeError("Runtime metadata is too large")

        for value in _values_for_key(body, "snapshot_override"):
            if (
                _serialized_size(value)
                > self._settings.runtime_max_snapshot_override_bytes
            ):
                raise PayloadTooLargeError("Runtime snapshot override is too large")
