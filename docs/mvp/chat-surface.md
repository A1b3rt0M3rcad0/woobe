# ChatSurface MVP

ChatSurface publishes one immutable Production Agent Release or Network Release
as an embeddable conversation. The integrator keeps permanent credentials on
its backend and gives the browser only a short-lived token bound to one
Surface, Session, origin, credential and immutable Release.

## Domain contract

A ChatSurface keeps both the logical target and the Release currently selected
for new Sessions:

```text
ChatSurface
  -> target_type + target_id
  -> target_release_id
```

Creating a Surface captures the target's current Production Release. Updating
the Surface through `POST /chat-surfaces/{surface_id}/release` captures the
current Production Release again.

This update affects only Sessions created afterward. Every Session binding
stores its own `target_release_id` and never follows later Production changes:

```text
Session A -> Release v1
Surface   -> updated to Release v2
Session A -> remains on Release v1
Session B -> opens on Release v2
```

Agent Sessions persist `opened_release_id` and `loaded_release_id`. Network
Sessions persist `network_version_id`. Runs are rejected when those bindings do
not match the ChatSurface Session binding or token.

## Security boundary

- `woobe_surface_*` is a permanent ChatSurface Access Key. It is returned once
  and stored only as a SHA-256 digest in `core.api_keys`.
- A Session token is an HS256 token with a default 15-minute TTL. It includes
  Project, Surface, logical target, immutable target Release, Session, allowed
  host origin, issuing credential and the current Surface token epoch.
- The iframe keeps the Session token in memory. It does not use cookies,
  `localStorage`, Runtime Keys or Project Keys.
- Every browser request sends `X-Woobe-Host-Origin`. The API compares it with
  the signed token claim; the loader and iframe validate both ends of
  `postMessage`.
- Disabling or archiving a Surface increments `token_epoch`. Revoking an Access
  Key invalidates every Session token issued by that credential.
- Streaming requires both `chat:send` and `chat:stream`.

Configure a signing key distinct from the administrative authentication key:

```dotenv
PROJECTRAI_CHAT_SURFACE_ENABLED=true
PROJECTRAI_CHAT_TOKEN_SIGNING_KEY=<at-least-32-random-bytes>
PROJECTRAI_CHAT_TOKEN_ISSUER=projectrai-chat
PROJECTRAI_CHAT_TOKEN_AUDIENCE=projectrai-chat-embed
PROJECTRAI_CHAT_TOKEN_TTL_SECONDS=900
PROJECTRAI_CORS_ORIGINS=https://control.woobe.ai,https://chat.woobe.ai
```

Production configuration rejects a missing, weak or reused ChatSurface signing
key.

## Backend integration

Create a Session idempotently:

```http
POST /v1/chat-surfaces/{public_id}/sessions
Authorization: Bearer woobe_surface_...
Idempotency-Key: local-conversation-id
Content-Type: application/json

{"external_reference":"local-conversation-id"}
```

Store the returned `session_id` against the authenticated user in the
integrator database. The response also contains the immutable
`target_release_id` used by that Session.

To open or resume the conversation, issue a fresh token:

```http
POST /v1/chat-surfaces/{public_id}/sessions/{session_id}/tokens
Authorization: Bearer woobe_surface_...
Content-Type: application/json

{"origin":"https://app.example.com"}
```

The integrator must validate its local user-to-Session ownership before calling
this endpoint. Token expiration never recreates or migrates the Session.

## Browser integration

The standard container publishes:

```text
/chat/v1/embed.js
/chat/v1/iframe.html
/chat/v1/assets/*
```

`embed.js` is the stable loader. Hashed JavaScript and CSS assets are immutable.
The loader resolves `iframe.html` relative to its own script URL, so the same
build works on `chat.woobe.ai`, a CDN or a self-hosted deployment.

```html
<div id="support-chat"></div>
<script src="https://chat.woobe.ai/chat/v1/embed.js"></script>
<script>
  const chat = WoobeChat.mount({
    container: "#support-chat",
    surfaceId: "csf_...",
    sessionToken: tokenReturnedByYourBackend,
    apiBaseUrl: "https://api.woobe.ai",
    mode: "inline",
    onEvent(event) {
      if (event.type === "session.expired") {
        // Fetch a fresh token from the integrator backend, then:
        // chat.updateToken(freshToken)
      }
    },
  });
</script>
```

For the bundled local stack:

```text
http://localhost:8081/chat/v1/embed.js
```

The API CORS allowlist must include the embed origin because browser requests
originate inside the hosted iframe. The Surface `allowed_origins` list remains
the allowlist of applications permitted to host that Surface.

## Appearance

The control plane validates and persists a constrained appearance contract:

```json
{
  "theme": "system",
  "primary_color": "#5B47E0",
  "title": "Product support",
  "placeholder": "Type a message…",
  "welcome_message": "How can I help?"
}
```

Only `light`, `dark` and `system` themes and exact `#RRGGBB` colors are
accepted. Arbitrary CSS is not accepted. The iframe loads this configuration
through the Session-authorized endpoint:

```http
GET /v1/chat/sessions/{session_id}/surface
Authorization: Bearer <SESSION_ACCESS_TOKEN>
X-Woobe-Host-Origin: https://app.example.com
```

Visual changes are mutable and affect future iframe loads. They do not change
the Session Release or runtime semantics.

## Runtime and observability

Agent Runs receive the Session's immutable `loaded_release_id`. Network Runs
use the Session's immutable `network_version_id`; they never read the current
Production pointer after Session creation.

ChatSurface execution attribution includes:

- `origin = chat_surface`;
- `chat_surface_id`;
- Session ID;
- immutable target Release ID;
- embed protocol version for Agent Runs;
- Network version, Surface and origin in Network execution events and outbox
  metadata.

History is read from Agent or Network message storage through the validated
Session binding. The iframe emits `ready`, `history.loaded`, `message.sent`,
`run.started`, `run.completed`, `session.expired` and `error`.

## Deployment

The bundled stack includes a `chat-embed` service. The API service receives all
ChatSurface token and rate-limit settings explicitly from `docker-compose.yml`.

```bash
cp .env.example .env
docker compose up --build -d
```

Relevant local endpoints:

```text
Control plane: http://localhost:5173
API:           http://localhost:8000
Chat embed:    http://localhost:8081/chat/v1/embed.js
```

Production should place the embed container behind the Woobe chat/CDN domain,
keep the API on its API domain and configure exact CORS, trusted-host and
Surface-origin allowlists. Static CSP protects the embed document; Session
token and `postMessage` origin validation remain the authorization boundary.

## Operational boundaries

The MVP supports exact HTTPS origins, one active Run per Session, per-Surface
request/concurrency limits, idempotent Session/message creation, Agent SSE,
persisted Network SSE reconnection, inline/floating modes, controlled themes,
Access Key rotation/revocation, Surface disable/archive and Session archive.

Anonymous public mode, custom domains, headless SDKs, delegated Tool identity,
external Staging embeds, human handoff and automatic Session migration are not
part of this delivery.

## Acceptance criteria

The implementation is acceptable when all of the following hold:

1. Creating a Surface captures a concrete Production Release.
2. Refreshing the Surface Release changes only new Sessions.
3. Existing Agent and Network Sessions continue on their opening Release.
4. A token for one Session cannot read or execute another Session.
5. A token cannot cross Surface, logical target, Release or origin boundaries.
6. Expired tokens can be renewed without losing history.
7. Access Key revocation and Surface disable invalidate browser access.
8. No ChatSurface Access Key is present in browser code or storage.
9. Appearance configured in the control plane is rendered by the iframe.
10. Agent and Network Runs expose Surface, Session and immutable Release
    attribution.
