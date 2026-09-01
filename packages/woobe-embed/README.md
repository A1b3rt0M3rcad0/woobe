# Woobe ChatSurface Embed

Browser-facing ChatSurface artifact distributed independently from the administrative Woobe frontend.

This package owns the iframe runtime, loader, browser protocol, presentation assets, and embed-specific tests. It consumes Woobe HTTP/streaming contracts and does not import Python Core.

From the repository root:

```bash
cd packages/woobe-embed
npm ci
npm run typecheck
npm test
npm run build
```

The supported Community deployment exposes this artifact through the `chat-embed` service in root `compose.yaml`.
