# Quick Start — ProjectRAI Frontend

## Prerequisites

- Node.js 18+
- Backend running on `http://localhost:8000`

## Setup

From the repository root:

```bash
cp .env.web.example .env.web
```

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

## Run with Docker Compose

Docker Compose uses the root `.env.web` file as a build secret and mounts it as `web/.env` only while building the static Vite bundle.

```bash
docker compose build web
docker compose up web
```

## Seed demo data

```bash
cd web
npm run seed
```

Login: `customer@gmail.com` / `customer`

## Build

```bash
cd web
npm run build
```

Output in `web/dist/`.
