# Compose test workflow

Woobe keeps product deployment and validation as separate contracts:

```text
compose.yaml        Community self-host distribution
compose.test.yaml   development/test validation stack
deploy/dev/          optional contributor infrastructure
```

`compose.test.yaml` is standalone. It does not depend on Bash, WSL, `scripts/test.sh`, another Compose file, or a separate test env file.

## Full validation

From the repository root, on PowerShell, CMD, Linux, or macOS:

```bash
docker compose -f compose.test.yaml run --rm tests
```

The `tests` service waits for the backend, frontend, mocked-browser, and full-stack browser suites to complete successfully.

For a deterministic fresh full-stack database between repeated local runs, tear down the test project first:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
docker compose -f compose.test.yaml run --rm tests
```

The test project is named `woobe-test`, so it remains isolated from the default Community Compose project.

## Individual suites

```bash
docker compose -f compose.test.yaml run --rm backend-tests
docker compose -f compose.test.yaml run --rm frontend-tests
docker compose -f compose.test.yaml run --rm browser-mocked
docker compose -f compose.test.yaml run --rm browser-e2e
```

`backend-tests` runs Ruff, Pyright, Alembic upgrade/check/rollback/re-upgrade, and the Python test suite. `frontend-tests` runs Vitest and the production Web build. `browser-mocked` keeps deterministic API interception for UI states that are expensive or awkward to create through a live backend. `browser-e2e` runs Playwright against the real Web/API boundary.

## Test topology

The standalone test stack includes PostgreSQL + pgvector, a separate PostgreSQL database service for backend tests, PgBouncer, RabbitMQ, Redis, MinIO, migrations, API, Workers, Web, ChatSurface, and a deterministic OpenAI-compatible fake provider.

Infrastructure state is test-only. PostgreSQL, RabbitMQ, and MinIO use ephemeral container storage rather than the persistent volumes used by Community. The full-stack Web and browser communicate through Docker Compose service DNS (`web`, `api`, `chat-embed`); no `host.docker.internal` or WSL integration is required.

The fake provider is test infrastructure, not a special production runtime mode. Product flows that need an LLM should use Woobe's existing OpenAI-compatible provider contract and point its Base URL at the fake service from inside the Compose network.

## CI

The manual `tests.yml` workflow validates `compose.test.yaml` and executes the same `docker compose -f compose.test.yaml run --rm tests` contract. It always removes any stale stack before the run, captures Compose status/logs on failure, tears the stack down afterward, and uploads `.test-artifacts` when present.

Community release acceptance remains separate and continues to validate the actual `compose.yaml` distribution.