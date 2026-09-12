# Self-hosting Woobe Core

Woobe Core uses one supported default self-host contract: the root `compose.yaml`.

## First start

```bash
python scripts/generate_self_host_env.py
docker compose up -d --build
```

The generator creates `.env` from `.env.example` and replaces sensitive bootstrap values with independent random secrets. It refuses to overwrite an existing `.env` unless `--force` is explicitly supplied.

Default endpoints:

```text
Web UI:     http://localhost:8080
API:        http://localhost:8000
ChatSurface: http://localhost:8081
```

The first registration against a fresh database claims the instance atomically and creates the first Instance Owner and initial Organization. Subsequent registration follows the configured signup/invite policy.

## Persistent state

The default topology persists PostgreSQL application/read-model state, the MongoDB Run event journal and checkpoints, RabbitMQ state, Redis runtime state and local Knowledge files.

`event_journal` is the default Run persistence mode. PostgreSQL keeps Run identity and relational/read-model data, MongoDB stores the incremental durable execution journal, and Redis provides hot runtime state plus the Redis -> Mongo persistence buffer. The supported Compose enables Redis AOF with `appendfsync=everysec`; that reduces the pre-Mongo loss window but does not make Redis the authoritative durable Run store. Events that require a durability barrier are acknowledged by the runtime only after the MongoDB journal reports the required contiguous sequence.

`WOOBE_RUN_PERSISTENCE_MODE=legacy_finalization` remains an explicit compatibility/rollback path. Do not use implicit fallback from `event_journal` when MongoDB is unavailable; a deployment configured for the journal should fail readiness/startup rather than silently change persistence semantics.

Back up PostgreSQL, MongoDB and Knowledge storage together as the durable product state. RabbitMQ and Redis still need operational recovery procedures, but they must not be treated as substitutes for those durable stores.

## Production configuration

Production is an environment configuration of the same Core topology, not a second Compose distribution.

Before public exposure, configure strong independent secrets, secure cookies, exact HTTPS CORS origins, exact trusted hosts and TLS termination.

After updating `.env`, rebuild Web when public `VITE_*` values change:

```bash
docker compose up -d --build
```

## Optional contributor topology

`deploy/dev/compose.yml` is an explicit contributor extension for exercising optional infrastructure locally. It is not the default Core deployment contract.

## Backup and restore

Use the repository backup/restore procedures documented in [PostgreSQL backup and restore](runbooks/postgres-backup-restore.md). Include MongoDB Run journal/checkpoint data and Knowledge storage in the same recovery plan. Until a dedicated MongoDB backup helper is shipped, operators must use the backup facilities appropriate to their MongoDB deployment and validate restore alongside PostgreSQL.

See [UPGRADING.md](UPGRADING.md).

## Security

Provider credentials, Tool credentials, Runtime Keys, ChatSurface Access Keys, session tokens, authentication secrets, encryption material and database/broker credentials must be treated as secrets.

Never publish a generated `.env`. Review [SECURITY.md](../SECURITY.md) before exposing a Core instance to the internet.
