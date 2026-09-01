# Woobe Frontend

Administrative control-plane frontend for Woobe. The ChatSurface browser artifact is a separate product package at `packages/woobe-embed`.

## Prerequisites

- Node.js 22+
- root `.env` generated from `.env.example`
- backend reachable at `VITE_API_URL`
- ChatSurface embed reachable at `VITE_CHAT_EMBED_URL`

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

## Docker Compose

```bash
python scripts/generate_self_host_env.py --force
docker compose up -d --build
```

## License

`woobe-frontend` is part of Woobe Core and is licensed under the **Woobe Core Sustainable Use License 1.0** in repository-root `LICENSE.md`, except third-party components or files carrying their own license notice. Woobe name/logo usage is separately governed by `TRADEMARKS.md`.
