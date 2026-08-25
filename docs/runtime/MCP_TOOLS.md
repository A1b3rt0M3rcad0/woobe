# Woobe MCP Tools

Woobe supports remote MCP providers over `streamable_http`. MCP providers are Project-scoped Tools; discovered remote tools are capabilities of that provider and are governed before being exposed to an Agent.

## Supported lifecycle

1. Register the MCP provider URL.
2. Run MCP `initialize` and `notifications/initialized`.
3. Run `tools/list` and persist discovered tools.
4. Keep each discovered tool in `review`, `allow` or `deny` policy.
5. Expose only `allow` tools to the model.
6. Route allowed `tools/call` through Woobe's guarded HTTP execution boundary.
7. Cache `Mcp-Session-Id` per Agent Session/provider when Redis-backed session cache is enabled; continue without cache when it is disabled or unavailable according to runtime policy.
8. Support OAuth connection after the provider has been created, including PKCE and device-code flows where advertised by the provider.

Currently out of scope: stdio MCP servers, marketplace/templates, per-end-user OAuth ownership and implicit per-call approval dialogs.

## OAuth model

OAuth belongs to the MCP provider, not to an Agent attachment. Woobe stores sensitive OAuth material encrypted on the provider configuration and retries authenticated discovery after successful connection.

Endpoints:

```text
POST /tools/mcp/oauth/start
POST /tools/mcp/oauth/complete
POST /tools/mcp/oauth/device/start
POST /tools/mcp/oauth/device/poll
POST /tools/mcp/oauth/status
POST /tools/mcp/oauth/disconnect
```

Do not treat `OAuth: connected` as equivalent to MCP readiness. Readiness requires authenticated `initialize` and `tools/list` to succeed.

## Permission policy

Newly discovered tools default to `review`. `allow` exposes the tool to the model and permits runtime execution; `deny` keeps it unavailable and blocks direct execution. Rediscovery preserves existing policy by remote tool name and introduces newly discovered tools as `review`.

Permission endpoints:

```text
PATCH /tools/mcp/permissions
POST /tools/mcp/permissions/bulk
```

## Environment

```env
WOOBE_REDIS_URL=redis://redis:6379/0
WOOBE_REDIS_CONNECT_TIMEOUT_SECONDS=2.0
WOOBE_MCP_SESSION_CACHE_ENABLED=true
WOOBE_MCP_SESSION_KEY_PREFIX=woobe:mcp-session
WOOBE_MCP_SESSION_TTL_SECONDS=3600
```

Woobe Community disables Redis-backed MCP session caching by default to keep the first-run topology small. Deployments that explicitly provide Redis can enable it when required.

## Security

Never log MCP session IDs, Authorization headers, API keys, OAuth code/state/verifier, device codes, access tokens, refresh tokens or unredacted sensitive request/response bodies. MCP remote calls use the same guarded outbound HTTP boundary as HTTP Tools and must not bypass private-network or redirect protections.
