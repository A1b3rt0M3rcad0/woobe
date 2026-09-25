# Woobe Frontend

Administrative control-plane frontend for Woobe. The ChatSurface browser artifact is a separate product package at `packages/woobe-embed`.

## Prerequisites

- Node.js 22+
- root `.env` generated from `.env.example`
- backend reachable at `WOOBE_PUBLIC_API_URL` for the container runtime
- ChatSurface embed reachable at `WOOBE_PUBLIC_CHAT_EMBED_URL` for the container runtime
- `VITE_API_URL` and `VITE_CHAT_EMBED_URL` remain local development/build fallbacks only

## Setup

From the repository root:

```bash
python scripts/generate_self_host_env.py --force
cd packages/woobe-frontend
npm ci
npm run dev
```

Only `VITE_*` values are embedded in the browser bundle; backend secrets must never be passed to the frontend.

The Core build uses `VITE_WOOBE_EDITION=core`.

## Published container

The deployable image is `ghcr.io/a1b3rt0m3rcad0/woobe-frontend:<VERSION>`. Configure `WOOBE_PUBLIC_API_URL` and `WOOBE_PUBLIC_CHAT_EMBED_URL` at container startup; rebuilding the image is not required when those public origins change.

See [`docs/runbooks/container-packages.md`](../../docs/runbooks/container-packages.md) for complete pull and runtime configuration examples.

## Docker Compose

```bash
python scripts/generate_self_host_env.py --force
docker compose up -d --build
```

## License

`woobe-frontend` is part of Woobe Core and is licensed under the **Woobe Core Sustainable Use License 1.0** in repository-root `LICENSE.md`, except third-party components or files carrying their own license notice. Woobe name/logo usage is separately governed by `TRADEMARKS.md`.
