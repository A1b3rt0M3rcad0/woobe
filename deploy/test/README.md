# Test deployment

`deploy/test/compose.yml` is a validation overlay, not a Woobe distribution.

It is intended to be combined with the supported Community Compose and the contributor development overlay:

```bash
docker compose \
  --env-file deploy/test/test.env \
  -p woobe-test \
  -f compose.yaml \
  -f deploy/dev/compose.yml \
  -f deploy/test/compose.yml \
  config
```

Use `scripts/test.sh` instead of invoking the files directly for normal validation. The script keeps local and GitHub Actions execution on the same contract.

Available suites:

```bash
sh scripts/test.sh backend
sh scripts/test.sh frontend
sh scripts/test.sh mocked
sh scripts/test.sh e2e
sh scripts/test.sh all
```

The test topology adds deterministic test runners and a fake OpenAI-compatible LLM to the development-like infrastructure. It exercises PostgreSQL/pgvector, PgBouncer, RabbitMQ, Redis, MinIO, migrations, API, Workers, Web and ChatSurface without requiring external provider credentials.

`mocked` runs the browser suite with intercepted API responses for deterministic UI states. `e2e` resets the test volumes, starts the real Woobe stack and runs Playwright against the real Web/API boundary. The Community distribution itself continues to be validated separately through `compose.yaml` acceptance/smoke checks.
