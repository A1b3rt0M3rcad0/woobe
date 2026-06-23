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

Out of scope for MVP:

- `stdio` MCP servers.
- Full SSE runtime support.
- MCP marketplace/templates.
- Background discovery jobs.
- Redis connection pooling through an external dependency.

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

## Security notes

Do not log:

- `Mcp-Session-Id`
- `Authorization`
- API keys
- sensitive headers
- full request/response bodies

HTTP and MCP remote calls both go through the guarded HTTP executor, which blocks non-public targets, private/loopback networks, DNS rebinding, and redirects.
