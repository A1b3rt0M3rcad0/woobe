# Woobe Frontend — Quick Start

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

## Docker Compose

For the supported Community first-run topology, from the repository root:

```bash
python scripts/generate_self_host_env.py --force
docker compose up -d --build
```

The browser calls `VITE_API_URL` directly. ChatSurface assets and iframe runtime use `VITE_CHAT_EMBED_URL` and are built from `packages/woobe-embed`.

## Demo bootstrap

Woobe does not ship fixed demo credentials. Provide your own values:

```bash
WOOBE_DEMO_EMAIL=owner@example.com \
WOOBE_DEMO_PASSWORD='use-a-strong-password' \
python scripts/seed_demo.py
```

This only initializes a fresh Community instance. Existing installations require the explicit owner-bootstrap flow documented in `docs/SELF_HOSTING.md`.
