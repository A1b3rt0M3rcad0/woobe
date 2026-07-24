# Quick Start — ProjectRAI Frontend

## Prerequisites

- Node.js 18+
- Backend running on the URL configured in the root `.env.web` file

## Setup

From the repository root:

```bash
cp .env.web.example .env.web
```

`.env.web` is intentionally frontend-only. Keep only public `VITE_*` values in it; backend/database/RabbitMQ secrets belong in the root `.env`.

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

The frontend opens at `http://localhost:5173`.

The Vite scripts run with `--mode web`, and `web/vite.config.ts` points `envDir` to the repository root, so frontend config is read from root `.env.web`.

## Run with Docker Compose

From the repository root, prepare both environment files:

```bash
cp .env.example .env
cp .env.web.example .env.web
docker compose up --build web
```

Docker BuildKit mounts only `.env.web` into the frontend builder. The backend `.env` is never exposed to the frontend build.

## Seed demo data

```bash
cd web
npm run seed
```

Login: `customer@gmail.com` / `customer`

## Build

From the repository root, `.env.web` must exist. Then:

```bash
cd web
npm run build
```

Output in `web/dist/`.
