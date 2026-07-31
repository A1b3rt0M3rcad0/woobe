# ChatSurface MVP

ChatSurface publishes one Production Agent or Network as an embeddable
conversation. The integration keeps permanent credentials on the integrator
backend and gives the browser only a short-lived token bound to one Surface,
Session, origin and credential.

## Security boundary

- `woobe_surface_*` is a permanent ChatSurface Access Key. It is returned once
  and stored only as a SHA-256 digest in `core.api_keys`.
- A Session token is an HS256 token with a default 15-minute TTL. It includes
  the Project, Surface, target, Session, allowed host origin, issuing
  credential and the current Surface token epoch.
- The iframe keeps the Session token in memory. It does not use cookies,
  `localStorage`, Runtime Keys or Project Keys.
- Every browser request must send `X-Woobe-Host-Origin`. The API compares it
  with the signed token claim; the embed also validates both ends of
  `postMessage`.
- Disabling or archiving a Surface increments `token_epoch`. Revoking an Access
  Key invalidates all Session tokens issued by that credential.

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
integrator database. To open or resume the conversation, issue a fresh token:

```http
POST /v1/chat-surfaces/{public_id}/sessions/{session_id}/tokens
Authorization: Bearer woobe_surface_...
Content-Type: application/json

{"origin":"https://app.example.com"}
```

## Browser integration

Serve the immutable embed assets and mount the stable loader:

```html
<div id="support-chat"></div>
<script src="https://cdn.woobe.ai/chat/v1/embed.js"></script>
<script>
  const chat = WoobeChat.mount({
    container: "#support-chat",
    surfaceId: "csf_...",
    sessionToken: tokenReturnedByYourBackend,
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

`embed/vite.config.ts` emits a manifest and content-hashed assets. Publish
source maps privately. The iframe route must be served with a dynamic
`Content-Security-Policy: frame-ancestors ...` generated from the Surface's
exact origin allowlist; do not relax the administrative application's framing
policy.

## Release behavior

`opened_release_id` and `network_version_id` remain the versions that opened
the Session. Each new ChatSurface Run resolves the current Production release
or version and records that effective execution binding. Non-ChatSurface
Sessions preserve their existing pinned behavior.

## Operational boundaries

The MVP supports exact HTTPS origins, one active Run per Session, per-Surface
request/concurrency limits, idempotent Session/message creation, Agent SSE and
persisted Network SSE reconnection. Anonymous public mode, custom domains,
headless SDKs, delegated Tool identity and external Staging embeds are not in
this delivery.
