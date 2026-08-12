# Quick Start — ProjectRAI Frontend

## Prerequisites

- Node.js 18+
- Root `.env` created from `.env.example`
- Backend reachable at `VITE_API_URL`

## Setup

From the repository root:

```bash
cp .env.example .env
```

`VITE_API_URL` lives in the same deployment manifest as the other service endpoints. It is public by design: Vite embeds only `VITE_*` values in the browser bundle. Backend secrets are not passed to the frontend Docker build.

Then install frontend dependencies:

```bash
cd web
npm install
```

## Run locally with Vite

```bash
cd web
npm run dev
```

The frontend opens at `http://localhost:5173` by default.

The Vite scripts use the neutral `manifest` mode, and `web/vite.config.ts` points `envDir` to the repository root. This loads the canonical root `.env` without reusing the legacy `.env.web` or `.env.production` mode-specific files from older setups.

## Run with Docker Compose

From the repository root:

```bash
cp .env.example .env
docker compose up --build web
```

Docker Compose extracts only `VITE_API_URL` from `.env` and passes it as a public build argument. PostgreSQL, RabbitMQ, encryption and authentication secrets are not exposed to the frontend build.

The runtime Nginx serves only the SPA/static assets. The browser calls `VITE_API_URL` directly; routing to the API is therefore independent from Docker service names and can target another host/load balancer.

## Seed demo data

```bash
cd web
npm run seed
```

Login: `customer@gmail.com` / `customer`

## Build

With `VITE_API_URL` exported or available in the root `.env`:

```bash
cd web
npm run build
```

Output in `web/dist/`.
