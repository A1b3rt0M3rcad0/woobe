# Contributor deployment topology

The root `compose.yaml` is the supported Woobe Core self-host topology and should remain the default path for users.

This directory contains optional development extensions for contributors who need additional infrastructure locally.

Start it explicitly together with the Core topology:

```bash
python scripts/generate_self_host_env.py

docker compose \
  -f compose.yaml \
  -f deploy/dev/compose.yml \
  up -d --build
```

Do not add debugging services, observers or one-off infrastructure to the root Compose contract. Development-only infrastructure belongs here and should exist only while it represents a repeatable contributor need.
