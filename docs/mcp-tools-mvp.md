# MCP Tools MVP

## Scope

This MVP supports remote MCP servers over `streamable_http` only.

Supported flow:

1. Register an MCP server provider by URL.
2. Run MCP `initialize`.
3. Send `notifications/initialized`.
4. Run `tools/list`.
5. Persist `discovered_tools` on the provider config.
6. Expose each discovered tool as a separate model function.
7. Route selected functions back to the parent MCP provider through `__mcp_tool_name`.
8. Execute remote `tools/call`.
9. Cache `Mcp-Session-Id` by `agent_session_id + provider_id` when Redis is available.
10. Continue execution without cache when Redis is unavailable.
11. Connect OAuth-protected MCP providers from the provider card after the MCP provider exists.

Out of scope for MVP:

- `stdio` MCP servers.
- Full SSE runtime support.
- MCP marketplace/templates.
- Background discovery jobs.
- Redis connection pooling through an external dependency.
- Per-end-user OAuth ownership. The MVP stores MCP OAuth at project/provider level.

## MCP OAuth connect model

OAuth belongs to the MCP provider, not to the agent-tool attachment. The intended user flow is:

1. Create the MCP provider with its streamable HTTP URL.
2. Open the Tools page.
3. Click `Connect` on the MCP provider card.
4. ProjectRAI calls `/tools/mcp/oauth/start`.
5. ProjectRAI redirects the browser to the provider authorization URL.
6. The provider returns to `/tools/mcp/oauth/callback` with `code` and `state`.
7. The frontend calls `/tools/mcp/oauth/complete`.
8. ProjectRAI stores the OAuth connection on `tool.config.oauth` using encrypted sensitive values.
9. Runtime MCP calls merge the provider headers and OAuth connection headers before `initialize` and `tools/call`.

Available endpoints:

```text
POST /tools/mcp/oauth/start
POST /tools/mcp/oauth/complete
POST /tools/mcp/oauth/status
POST /tools/mcp/oauth/disconnect
```

The start flow supports PKCE, `resource`, authorization server metadata discovery, and dynamic client registration when the remote authorization server exposes a registration endpoint. When dynamic registration is not available, the frontend must pass `client_id` and optionally `client_secret`.

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
2. Connect a public MCP server over streamable HTTP.
3. Confirm discovered tools appear in the UI.
4. Test one discovered MCP tool with JSON input.
5. Save the MCP provider.
6. Ask an agent question that forces one discovered MCP tool call.
7. Repeat in the same session and confirm a session cache hit in logs.
8. Stop Redis and confirm MCP calls still work without cache.
9. Test an authenticated MCP server and confirm discovery refresh can resolve configured headers.
10. Test an OAuth MCP provider by clicking `Connect`, completing the provider auth screen, returning to the callback page, and executing a discovered tool.

## Security notes

Do not log:

- `Mcp-Session-Id`
- `Authorization`
- API keys
- sensitive headers
- full request/response bodies
- OAuth code/state/verifier values

HTTP and MCP remote calls both go through the guarded HTTP executor, which blocks non-public targets, private/loopback networks, DNS rebinding, and redirects.
