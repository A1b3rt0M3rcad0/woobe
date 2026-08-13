# Compose backend test workflow

Woobe keeps product deployment and backend validation as separate contracts:

```text
compose.yaml        Community self-host distribution
compose.test.yaml   backend validation stack
deploy/dev/          optional contributor infrastructure
```

`compose.test.yaml` is standalone and intentionally backend-only. It does not start or validate Web, ChatSurface, Vite, Vitest, Playwright, browser E2E, or any other frontend surface.

## Canonical command

Local development and GitHub Actions use the same command:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

The `tests` service is only an aggregate exit point. It completes when both backend suites complete successfully and propagates their result through the Compose command.

After a local run, clean the isolated test project with:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
```

The Compose project is named `woobe-test` and does not reuse the default Community stack.

## Test images

Each backend test type has its own Dockerfile:

```text
docker/tests/Dockerfile.backend-mocked
docker/tests/Dockerfile.backend-integration
```

### Mocked backend suite

`Dockerfile.backend-mocked` runs backend tests that must not depend on external infrastructure. It uses an isolated SQLite test database and executes:

```text
tests/modules
tests/contract
tests/fakes
tests/messaging
tests/editions
```

The suite writes JUnit evidence to:

```text
.test-artifacts/backend-mocked.xml
```

### Backend integration suite

`Dockerfile.backend-integration` validates the backend against real integration infrastructure supplied by Compose:

```text
PostgreSQL + pgvector
RabbitMQ
```

Before the integration suite, the runner applies the real Alembic migration chain required by the test database. It then executes only:

```text
tests/integration
```

The suite writes JUnit evidence to:

```text
.test-artifacts/backend-integration.xml
```

The integration environment deliberately uses local storage and disables the Redis-backed MCP session cache. Redis, MinIO, PgBouncer, API containers, Workers, Web, ChatSurface, fake browser services, and browser runners are not part of this test contract.

## Individual diagnosis

The two suites can be executed independently when diagnosing a failure:

```bash
docker compose -f compose.test.yaml run --rm --build backend-mocked
docker compose -f compose.test.yaml run --rm --build backend-integration
```

Logs must also select the test Compose file:

```bash
docker compose -f compose.test.yaml logs --no-color backend-mocked
docker compose -f compose.test.yaml logs --no-color backend-integration
```

## CI

`.github/workflows/tests.yml` validates this Compose file and executes exactly the same canonical command used locally:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

CI only adds lifecycle and evidence handling around that command: cleanup, Compose validation, failure logs, teardown, and artifact upload. It does not define a separate frontend test path.

Release/security/production acceptance remain separate concerns and are not part of this local/CI backend test contract.
