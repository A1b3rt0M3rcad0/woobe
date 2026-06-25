# Quick Start — ProjectRAI Frontend

## Prerequisites

- Node.js 18+
- Backend running on the URL configured in the root `.env.web` file

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

The Vite scripts run with `--mode web`, and frontend config is read from the root `.env.web` file.

## Run with Docker Compose

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
