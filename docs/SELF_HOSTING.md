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

The default topology persists PostgreSQL application state, RabbitMQ state, Redis state and local Knowledge files. Back up durable database and Knowledge state together.

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

Use the repository backup/restore procedures documented in [PostgreSQL backup and restore](runbooks/postgres-backup-restore.md). Include Knowledge storage in the same recovery plan.

See [UPGRADING.md](UPGRADING.md).

## Security

Provider credentials, Tool credentials, Runtime Keys, ChatSurface Access Keys, session tokens, authentication secrets, encryption material and database/broker credentials must be treated as secrets.

Never publish a generated `.env`. Review [SECURITY.md](../SECURITY.md) before exposing a Core instance to the internet.
