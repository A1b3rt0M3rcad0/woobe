# Woobe ChatSurface Embed

Browser-facing ChatSurface artifact distributed independently from the administrative Woobe frontend.

This package owns the iframe runtime, loader, browser protocol, presentation assets and embed-specific tests. It consumes Woobe HTTP/streaming contracts and does not import Python Core.

From the repository root:

```bash
cd packages/woobe-embed
npm ci
npm run typecheck
npm test
npm run build
```

The supported Core deployment exposes this artifact through the `chat-embed` service in root `compose.yaml`.

## License

`woobe-embed` is part of Woobe Core and is licensed under the **Woobe Core Sustainable Use License 1.0** in repository-root `LICENSE.md`, except third-party components or files carrying their own license notice. Woobe name/logo usage is separately governed by `TRADEMARKS.md`.
