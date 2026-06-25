from modules.agent.application.mcp_readiness import build_mcp_readiness


def test_public_mcp_without_discovery_shows_load_tools_not_connect() -> None:
    readiness = build_mcp_readiness({"protocol": "mcp", "discovered_tools": []})

    assert readiness["state"] == "needs_discovery"
    assert readiness["action"] == "refresh"
    assert readiness["label"] == "Load tools"


def test_public_mcp_with_allowed_tools_is_ready_without_oauth() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "mcp_status": "ready",
        "discovered_tools": [
            {"name": "search", "permission": {"mode": "allow"}},
        ],
    })

    assert readiness["state"] == "ready"
    assert readiness["action"] == "manage_tools"
    assert readiness["can_use_tools"] is True
    assert readiness["exposed_count"] == 1


def test_public_mcp_with_review_tools_needs_permission_without_oauth() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "mcp_status": "ready",
        "discovered_tools": [
            {"name": "search", "permission": {"mode": "review"}},
        ],
    })

    assert readiness["state"] == "needs_permission"
    assert readiness["action"] == "configure_permissions"
    assert readiness["can_use_tools"] is False


def test_oauth_protected_mcp_shows_connect_only_on_auth_challenge() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "mcp_status": "needs_connection",
        "discovered_tools": [],
        "mcp_discovery": {
            "status": "needs_connection",
            "http_status": 401,
            "www_authenticate": "Bearer resource_metadata=\"https://mcp.example.com/.well-known/oauth-protected-resource\"",
        },
    })

    assert readiness["state"] == "needs_connection"
    assert readiness["action"] == "connect"
    assert readiness["label"] == "Connect"


def test_connected_mcp_with_rejected_token_does_not_show_connect() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "oauth": {"status": "connected"},
        "discovered_tools": [],
        "mcp_discovery": {
            "status": "token_invalid",
            "http_status": 401,
        },
    })

    assert readiness["state"] == "token_rejected"
    assert readiness["action"] == "disconnect"
