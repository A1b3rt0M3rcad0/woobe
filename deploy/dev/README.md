# Contributor deployment topology

The root `compose.yaml` is the supported Woobe Community self-host topology and should remain the default path for users.

This directory contains an optional development extension for contributors who need to exercise Redis-backed MCP session caching, PgBouncer, and S3-compatible storage locally.

Start it explicitly together with the Community topology:

```bash
python scripts/generate_self_host_env.py

docker compose \
  -f compose.yaml \
  -f deploy/dev/compose.yml \
  up -d --build
```

Do not add debugging services, observers, or one-off infrastructure to the root Compose contract. Development-only infrastructure belongs here and should exist only while it represents a repeatable contributor need.
