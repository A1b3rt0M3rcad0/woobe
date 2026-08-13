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

Local development and GitHub Actions use the same execution contract:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

This starts the aggregate `tests` service together with its dependency graph. The aggregate service only completes after backend, frontend, mocked-browser, and full-stack browser suites complete successfully. `--exit-code-from tests` propagates the aggregate result and stops the attached Compose project when the aggregate service exits.

A bare `docker compose -f compose.test.yaml` is not executable because `-f` only selects the Compose file; Docker Compose still requires a subcommand such as `up`, `run`, or `down`.

After a local run, remove stopped test containers and any test state with:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
```

The test project is named `woobe-test`, so it remains isolated from the default Community Compose project.

## Dedicated test images

### Backend

`Dockerfile.backend` owns the backend validation sequence:

```text
Ruff (blocking)
  -> Full Pyright diagnostics (non-blocking repository baseline)
  -> Alembic upgrade/current/check -> rollback -> re-upgrade/check (blocking)
  -> Pytest (blocking)
```

The repository-wide Pyright pass remains visible but does not currently fail the aggregate validation when it returns type diagnostics. Its output is printed to the container log and persisted as `.test-artifacts/backend-pyright.log`. A Pyright execution failure distinct from normal type diagnostics still fails the backend runner. This preserves the existing project contract while the repository-wide type baseline is reduced separately.

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

Individual suites remain available for focused local diagnosis:

```bash
docker compose -f compose.test.yaml run --rm --build backend-tests
docker compose -f compose.test.yaml run --rm --build frontend-tests
docker compose -f compose.test.yaml run --rm --build browser-mocked
docker compose -f compose.test.yaml run --rm --build browser-e2e
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

The fake provider is test infrastructure, not a special production runtime mode. Product flows that need an LLM should use Woobe's existing OpenAI-compatible provider contract and point its Base URL at the fake service from inside the Compose network.

## CI

The manual `tests.yml` workflow validates `compose.test.yaml` and then executes exactly the same command documented for local full validation:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

CI only adds lifecycle concerns around that command: stale-stack cleanup before the run, diagnostics on failure, final teardown, and artifact upload. The actual validation entrypoint is identical locally and in CI.

Community release acceptance remains separate and continues to validate the actual `compose.yaml` distribution.
