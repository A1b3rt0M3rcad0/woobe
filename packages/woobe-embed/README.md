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

## External Context

The Embed can attach request-side `external_context` values to each ChatSurface message. The values are validated by the External Context contract frozen into the pinned Agent or Network Release.

```js
const chat = window.WoobeChat.mount({
  container: "#support",
  surfaceId: "surface_...",
  sessionToken: "...",
  externalContext: {
    customer_name: "Mariana Costa",
    plan: "business",
    current_page: "/billing/subscription",
  },
});
```

The current context can be replaced without remounting the iframe. The replacement is used by the next submitted message:

```js
chat.setExternalContext({
  customer_name: "Mariana Costa",
  plan: "business",
  current_page: "/billing/invoices",
});
```

`setExternalContext()` uses replacement semantics rather than merging with the previous object. Embed-provided values originate in the browser and should not be treated as credentials, secrets, or an authorization boundary.

## License

`woobe-embed` is part of Woobe Core and is licensed under the **Woobe Core Sustainable Use License 1.0** in repository-root `LICENSE.md`, except third-party components or files carrying their own license notice. Woobe name/logo usage is separately governed by `TRADEMARKS.md`.
