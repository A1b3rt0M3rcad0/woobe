import pytest

from woobe_api.security.control_plane_permissions import control_plane_permission


@pytest.mark.parametrize(
    ("method", "path", "permission"),
    [
        ("GET", "/core/workspaces/00000000-0000-0000-0000-000000000001/control-keys", "keys:read"),
        ("POST", "/core/workspaces/00000000-0000-0000-0000-000000000001/control-keys", "keys:create"),
        ("POST", "/core/workspaces/00000000-0000-0000-0000-000000000001/control-keys/00000000-0000-0000-0000-000000000002/revoke", "keys:revoke"),
        ("PATCH", "/core/projects/00000000-0000-0000-0000-000000000001", "project:update"),
        ("PUT", "/core/projects/00000000-0000-0000-0000-000000000001/environment-keys/API_KEY", "project:environment:write"),
        ("GET", "/core/projects/00000000-0000-0000-0000-000000000001/api-keys", "api_key:read"),
        ("POST", "/core/projects/00000000-0000-0000-0000-000000000001/runtime-keys", "api_key:write"),
        ("POST", "/core/projects/00000000-0000-0000-0000-000000000001/api-keys/00000000-0000-0000-0000-000000000002/rotate", "api_key:write"),
        ("POST", "/ai/agents", "agent:write"),
        ("POST", "/ai/agents/00000000-0000-0000-0000-000000000001/releases", "agent:version"),
        ("POST", "/ai/agents/00000000-0000-0000-0000-000000000001/releases/00000000-0000-0000-0000-000000000002/promote", "agent:production"),
        ("DELETE", "/ai/agents/00000000-0000-0000-0000-000000000001", "agent:delete"),
        ("DELETE", "/knowledge/collections/00000000-0000-0000-0000-000000000001", "knowledge:delete"),
        ("DELETE", "/ai/credentials/00000000-0000-0000-0000-000000000001", "provider:delete"),
        ("DELETE", "/ai/provider-models/00000000-0000-0000-0000-000000000001", "model:delete"),
        ("DELETE", "/tools/tools/00000000-0000-0000-0000-000000000001", "tool:delete"),
        ("DELETE", "/network/projects/00000000-0000-0000-0000-000000000001/networks/00000000-0000-0000-0000-000000000002", "network:delete"),
        ("GET", "/chat-surfaces/projects/00000000-0000-0000-0000-000000000001", "chat_surface:read"),
        ("POST", "/chat-surfaces/projects/00000000-0000-0000-0000-000000000001", "chat_surface:write"),
        ("POST", "/chat-surfaces/00000000-0000-0000-0000-000000000001/release", "chat_surface:release"),
        ("POST", "/chat-surfaces/00000000-0000-0000-0000-000000000001/access-keys", "chat_surface:keys"),
        ("POST", "/network/00000000-0000-0000-0000-000000000001/promotions", "network:production"),
        ("GET", "/agent/knowledge/collections/00000000-0000-0000-0000-000000000001/overview", "knowledge:read"),
    ],
)
def test_management_routes_require_explicit_control_permission(
    method: str,
    path: str,
    permission: str,
) -> None:
    assert control_plane_permission(method, path) == permission


def test_runtime_routes_are_not_implicitly_opened_to_control_keys() -> None:
    assert control_plane_permission("POST", "/v1/run") is None
    assert control_plane_permission("POST", "/agent/runtime/ask") is None
    assert (
        control_plane_permission(
            "POST",
            "/v1/chat-surfaces/public-id/sessions",
        )
        is None
    )
    assert (
        control_plane_permission(
            "POST",
            "/v1/chat/sessions/00000000-0000-0000-0000-000000000001/messages:stream",
        )
        is None
    )
