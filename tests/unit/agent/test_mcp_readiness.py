from modules.agent.application.interfaces.mcp_readiness import (
    build_mcp_readiness,
    classify_mcp_discovery_status,
    has_mcp_oauth_challenge,
    has_valid_mcp_oauth_metadata,
)


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


def test_oauth_protected_mcp_shows_connect_only_after_metadata_validation() -> None:
    config = {
        "protocol": "mcp",
        "mcp_status": "oauth_required",
        "discovered_tools": [],
        "mcp_discovery": {
            "status": "oauth_required",
            "http_status": 401,
            "www_authenticate": "Bearer resource_metadata=\"https://mcp.example.com/.well-known/oauth-protected-resource\"",
        },
        "mcp_oauth_discovery": {
            "status": "valid",
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
        },
    }

    readiness = build_mcp_readiness(config)

    assert has_valid_mcp_oauth_metadata(config) is True
    assert readiness["state"] == "needs_connection"
    assert readiness["action"] == "connect"
    assert readiness["label"] == "Connect"


def test_raw_oauth_challenge_without_validated_endpoints_does_not_show_connect() -> None:
    config = {
        "protocol": "mcp",
        "mcp_status": "oauth_required",
        "discovered_tools": [],
        "mcp_discovery": {
            "status": "oauth_required",
            "http_status": 401,
            "www_authenticate": "Bearer resource_metadata=\"https://mcp.example.com/.well-known/oauth-protected-resource\"",
        },
    }

    readiness = build_mcp_readiness(config)

    assert has_valid_mcp_oauth_metadata(config) is False
    assert readiness["state"] == "oauth_metadata_invalid"
    assert readiness["action"] == "review_provider"


def test_invalid_oauth_metadata_has_specific_readiness() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "mcp_status": "oauth_metadata_invalid",
        "discovered_tools": [],
        "mcp_oauth_discovery": {
            "status": "invalid_metadata",
            "error": "authorization endpoints missing",
        },
        "mcp_discovery": {
            "status": "oauth_metadata_invalid",
            "http_status": 401,
        },
    })

    assert readiness["state"] == "oauth_metadata_invalid"
    assert readiness["action"] == "review_provider"
    assert readiness["label"] == "OAuth metadata invalid"


def test_managed_provider_does_not_show_direct_oauth_connect() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "mcp_status": "provider_managed",
        "discovered_tools": [],
        "mcp_oauth_discovery": {
            "status": "provider_managed",
            "provider": "smithery",
        },
        "mcp_discovery": {
            "status": "provider_managed",
            "http_status": 401,
        },
    })

    assert readiness["state"] == "provider_managed"
    assert readiness["action"] == "provider_credentials"
    assert readiness["needs_provider_client"] is True
    assert "smithery" in readiness["message"]


def test_unauthorized_without_oauth_metadata_requires_static_credentials() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "mcp_status": "needs_credentials",
        "discovered_tools": [],
        "mcp_discovery": {
            "status": "needs_credentials",
            "http_status": 401,
            "www_authenticate": "Bearer realm=\"provider\"",
        },
    })

    assert readiness["state"] == "needs_credentials"
    assert readiness["action"] == "configure_credentials"
    assert readiness["label"] == "Credentials required"


def test_legacy_needs_connection_without_oauth_metadata_is_reclassified() -> None:
    readiness = build_mcp_readiness({
        "protocol": "mcp",
        "mcp_status": "needs_connection",
        "discovered_tools": [],
        "mcp_discovery": {
            "status": "needs_connection",
            "http_status": 401,
            "www_authenticate": None,
        },
    })

    assert readiness["state"] == "needs_credentials"
    assert readiness["action"] == "configure_credentials"


def test_basic_auth_challenge_is_not_treated_as_mcp_oauth() -> None:
    assert has_mcp_oauth_challenge('Basic realm="provider"') is False
    assert classify_mcp_discovery_status(
        has_tools=False,
        error="MCP initialize failed",
        http_status=401,
        www_authenticate='Basic realm="provider"',
    ) == "needs_credentials"


def test_bearer_challenge_without_resource_metadata_is_not_treated_as_mcp_oauth() -> None:
    assert has_mcp_oauth_challenge('Bearer realm="provider"') is False
    assert classify_mcp_discovery_status(
        has_tools=False,
        error="MCP initialize failed",
        http_status=401,
        www_authenticate='Bearer realm="provider"',
    ) == "needs_credentials"


def test_bearer_resource_metadata_challenge_is_only_preliminary_oauth_evidence() -> None:
    challenge = 'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"'

    assert has_mcp_oauth_challenge(challenge) is True
    assert classify_mcp_discovery_status(
        has_tools=False,
        error="MCP initialize failed",
        http_status=401,
        www_authenticate=challenge,
    ) == "oauth_required"


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


def test_discovery_status_distinguishes_endpoint_scope_and_availability_failures() -> None:
    assert classify_mcp_discovery_status(
        has_tools=False,
        error="not found",
        http_status=404,
        www_authenticate=None,
    ) == "invalid_endpoint"
    assert classify_mcp_discovery_status(
        has_tools=False,
        error="forbidden",
        http_status=403,
        www_authenticate=None,
    ) == "scope_denied"
    assert classify_mcp_discovery_status(
        has_tools=False,
        error="service unavailable",
        http_status=503,
        www_authenticate=None,
    ) == "unavailable"
