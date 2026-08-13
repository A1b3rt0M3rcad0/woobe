# Compose test workflow

Woobe keeps product deployment and validation as separate contracts:

```text
compose.yaml        Community self-host distribution
compose.test.yaml   development/test validation stack
deploy/dev/          optional contributor infrastructure
```

`compose.test.yaml` is standalone. It does not depend on Bash, WSL, `scripts/test.sh`, another Compose file, or a separate test env file.

The Compose file is an orchestrator only. Test runtime dependencies and test commands live in dedicated Dockerfiles under `docker/tests/`:

```text
docker/tests/Dockerfile.backend
docker/tests/Dockerfile.frontend
docker/tests/Dockerfile.browser-mocked
docker/tests/Dockerfile.browser-e2e
docker/tests/Dockerfile.fake-llm
```

The product Dockerfiles (`Dockerfile` and `web/Dockerfile`) contain production build/runtime concerns only. They do not expose test stages.

## Full validation

From the repository root, on PowerShell, CMD, Linux, or macOS:

```bash
docker compose -f compose.test.yaml run --rm tests
```

This is the shortest supported Docker Compose invocation that both selects the test contract and runs the one-shot aggregate test service. A bare `docker compose -f compose.test.yaml` is not executable because Docker Compose requires a subcommand.

The `tests` service waits for the backend, frontend, mocked-browser, and full-stack browser suites to complete successfully. A failing suite makes the aggregate command fail.

For a deterministic fresh full-stack database between repeated local runs:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
docker compose -f compose.test.yaml run --rm tests
```

The test project is named `woobe-test`, so it remains isolated from the default Community Compose project.

## Dedicated test images

### Backend

`Dockerfile.backend` owns the complete backend validation command:

```text
Ruff -> Pyright -> Alembic upgrade/current/check -> rollback -> re-upgrade/check -> Pytest
```

The image includes test-only system dependencies such as `libatomic1`, required by the Node runtime used by Pyright in the slim Python image. That dependency is intentionally not added to the production backend image.

### Frontend

`Dockerfile.frontend` owns:

```text
Vitest -> TypeScript/Vite production build
```

It uses the Web build context and does not depend on a test stage in `web/Dockerfile`.

### Browser mocked

`Dockerfile.browser-mocked` runs `playwright.config.ts` against a production-shaped Web container. API calls are intercepted by the Playwright suite for deterministic UI-state coverage.

### Browser full-stack

`Dockerfile.browser-e2e` runs `fullstack.config.ts` against the real Web/API boundary. Its dependency graph also starts the real worker process, PostgreSQL, PgBouncer, RabbitMQ, Redis, MinIO, migrations, ChatSurface, and the deterministic fake provider.

### Fake LLM

`Dockerfile.fake-llm` is a dedicated image for `tests.fakes.openai_provider`. It is test infrastructure and does not introduce a test mode into the production runtime.

## Individual suites

```bash
docker compose -f compose.test.yaml run --rm backend-tests
docker compose -f compose.test.yaml run --rm frontend-tests
docker compose -f compose.test.yaml run --rm browser-mocked
docker compose -f compose.test.yaml run --rm browser-e2e
```

For diagnostics, always select the test Compose file as well:

```bash
docker compose -f compose.test.yaml logs --no-color backend-tests
docker compose -f compose.test.yaml logs --no-color frontend-tests
docker compose -f compose.test.yaml logs --no-color browser-mocked
docker compose -f compose.test.yaml logs --no-color browser-e2e
```

## Test topology

The standalone test stack includes PostgreSQL + pgvector, a separate PostgreSQL service for backend tests, PgBouncer, RabbitMQ, Redis, MinIO, migrations, API, Workers, Web, ChatSurface, and a deterministic OpenAI-compatible fake provider.

Infrastructure state is test-only. PostgreSQL, RabbitMQ, and MinIO use ephemeral container storage rather than the persistent volumes used by Community. The full-stack Web and browser communicate through Docker Compose service DNS (`web`, `api`, `chat-embed`); no `host.docker.internal` or WSL integration is required.

The mocked browser suite uses a second production-shaped Web service (`web-mocked`) instead of a Vite preview process, keeping the browser test closer to the shipped frontend artifact while Playwright intercepts the API boundary.

The fake provider is test infrastructure, not a special production runtime mode. Product flows that need an LLM should use Woobe's existing OpenAI-compatible provider contract and point its Base URL at the fake service from inside the Compose network.

## CI

The manual `tests.yml` workflow validates `compose.test.yaml` and executes the same local contract:

```bash
docker compose -f compose.test.yaml run --rm tests
```

It removes any stale stack before the run, captures Compose status/logs on failure, tears the stack down afterward, and uploads `.test-artifacts` when present.

Community release acceptance remains separate and continues to validate the actual `compose.yaml` distribution.
