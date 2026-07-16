# MCP Tools MVP

## Scope

This MVP supports remote MCP servers over `streamable_http` only.

Supported flow:

1. Register an MCP server provider by URL. Discovery is optional at creation time so protected MCP servers can be saved before connection.
2. Run MCP `initialize`.
3. Send `notifications/initialized`.
4. Run `tools/list`.
5. Persist `discovered_tools` on the provider config when discovery succeeds.
6. Store a policy for each discovered tool: `review`, `allow`, or `deny`.
7. Expose only `allow` discovered tools as model functions.
8. Route selected functions back to the parent MCP provider through `__mcp_tool_name`.
9. Execute remote `tools/call` only when the selected discovered tool is allowed by policy.
10. Cache `Mcp-Session-Id` by `agent_session_id + provider_id` when Redis is available.
11. Continue execution without cache when Redis is unavailable.
12. Connect OAuth-protected MCP providers from the provider card after the MCP provider exists.
13. Prefer provider-advertised OAuth flow hints when a protected resource publishes multiple authorization servers.
14. Support OAuth device-code connection for providers that cannot or do not accept ProjectRAI redirect callbacks.

Out of scope for MVP:

- `stdio` MCP servers.
- Full SSE runtime support.
- MCP marketplace/templates.
- Background discovery jobs.
- Redis connection pooling through an external dependency.
- Per-end-user OAuth ownership. The MVP stores MCP OAuth at project/provider level.
- Per-call human approval. The MVP is policy-first and API-first.

## MCP OAuth connect model

OAuth belongs to the MCP provider, not to the agent-tool attachment. The intended browser callback flow is:

1. Create the MCP provider with its streamable HTTP URL. The provider can be saved even if unauthenticated discovery fails.
2. Open the Tools page.
3. Click `Connect` on the MCP provider card.
4. ProjectRAI calls `/tools/mcp/oauth/start`.
5. ProjectRAI redirects the browser to the provider authorization URL.
6. The provider returns to `/tools/mcp/oauth/callback` with `code` and `state`.
7. The frontend calls `/tools/mcp/oauth/complete`.
8. ProjectRAI stores the OAuth connection on `tool.config.oauth` using encrypted sensitive values.
9. ProjectRAI immediately retries MCP discovery with the connected provider token.
10. Runtime MCP calls merge the provider headers and OAuth connection headers before `initialize` and `tools/call`.
11. The callback returns to the Tools page with permission configuration expanded for that provider.

Available endpoints:

```text
POST /tools/mcp/oauth/start
POST /tools/mcp/oauth/complete
POST /tools/mcp/oauth/device/start
POST /tools/mcp/oauth/device/poll
POST /tools/mcp/oauth/status
POST /tools/mcp/oauth/disconnect
```

The start flow supports PKCE, `resource`, authorization server metadata discovery, provider authorization hints, and dynamic client registration when the remote authorization server exposes a registration endpoint. When dynamic registration is not available, the API caller must pass `client_id` and optionally `client_secret`.

For providers that advertise `client_capability_based` authorization or a `device_code` option, the backend exposes a device-code flow:

1. Call `/tools/mcp/oauth/device/start` with `tool_id`, optional `scopes`, and provider-issued `client_id`/`client_secret` when dynamic registration is not available.
2. Show `verification_uri_complete` when present; otherwise show `verification_uri` and `user_code`.
3. Poll `/tools/mcp/oauth/device/poll` no faster than the returned `interval` until the response status is `connected`, `authorization_pending`, `slow_down`, or `device_expired`.
4. On `connected`, ProjectRAI stores the encrypted token set and immediately retries authenticated MCP discovery.

Do not treat `OAuth: connected` as equivalent to MCP readiness. The authoritative readiness state is `mcp_status=ready` after authenticated `initialize` and `tools/list` succeed.

## MCP permission policy model

MCP discovered tools are controlled by policy, not by per-call approval prompts. Each discovered tool has:

```json
{
  "name": "create_video",
  "permission": {
    "mode": "review",
    "risk_level": "unknown"
  }
}
```

Supported modes:

- `review`: default for newly discovered tools. The tool is not exposed to the model and cannot execute until configured.
- `allow`: exposed to the model and executable by runtime.
- `deny`: not exposed to the model and blocked by runtime.

Permission endpoints:

```text
PATCH /tools/mcp/permissions
POST /tools/mcp/permissions/bulk
```

Examples:

```json
{
  "tool_id": "provider-tool-id",
  "permissions": [
    {"remote_tool_name": "create_video", "mode": "allow"},
    {"remote_tool_name": "delete_video", "mode": "deny"}
  ]
}
```

```json
{
  "tool_id": "provider-tool-id",
  "mode": "allow"
}
```

Rediscovery preserves any previous policy by discovered tool name. New server tools are added as `review`.

## Environment variables

```env
PROJECTRAI_REDIS_URL=redis://redis:6379/0
PROJECTRAI_REDIS_CONNECT_TIMEOUT_SECONDS=2.0
PROJECTRAI_MCP_SESSION_CACHE_ENABLED=true
PROJECTRAI_MCP_SESSION_KEY_PREFIX=projectrai:mcp-session
PROJECTRAI_MCP_SESSION_TTL_SECONDS=3600
```

`redis://` and `rediss://` URLs are supported. Redis URLs with username/password are authenticated before DB selection.

## Validation checklist

Run targeted unit tests first:

```bash
pytest tests/unit/agent/test_tool_runtime.py
pytest tests/unit/agent/test_mcp_tool_refresh.py
```

Then run the full suite:

```bash
pytest
```

Then validate the composed runtime:

```bash
docker compose up -d --build
```

Manual validation:

1. Create and test a normal HTTP tool.
2. Create a public MCP server and optionally run discovery during creation.
3. Create a protected MCP server without discovery, then connect it from the Tools page.
4. Confirm OAuth completion runs authenticated discovery and returns to permission configuration.
5. For a provider with device-code hints, call `/tools/mcp/oauth/device/start`, complete verification out of band, and poll `/tools/mcp/oauth/device/poll` until connected.
6. Confirm discovered tools appear in the UI as `review`.
7. Use `Allow all`, `Deny all`, and per-tool `Allow/Deny/Review` controls.
8. Confirm only allowed tools are exposed to agents.
9. Save the MCP provider.
10. Ask an agent question that forces one allowed discovered MCP tool call.
11. Confirm a denied/review tool is blocked if invoked directly.
12. Repeat in the same session and confirm a session cache hit in logs.
13. Stop Redis and confirm MCP calls still work without cache.
14. Test an authenticated MCP server and confirm discovery refresh can resolve configured headers and OAuth headers.

## Security notes

Do not log:

- `Mcp-Session-Id`
- `Authorization`
- API keys
- sensitive headers
- full request/response bodies
- OAuth code/state/verifier values
- OAuth device code
- access tokens
- refresh tokens

HTTP and MCP remote calls both go through the guarded HTTP executor, which blocks non-public targets, private/loopback networks, DNS rebinding, and redirects.
