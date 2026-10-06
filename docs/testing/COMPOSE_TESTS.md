# Compose backend test workflow

Woobe keeps product deployment and backend validation as separate contracts:

```text
compose.yaml        Woobe Core self-host distribution
compose.test.yaml   backend validation stack
deploy/dev/          optional contributor infrastructure
```

`compose.test.yaml` is standalone and intentionally backend-only. It does not start or validate Web, ChatSurface, Vite, Vitest, Playwright, browser E2E or any other frontend surface.

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

The Compose project is named `woobe-test` and does not reuse the default Core stack.

## Test images

Each backend test type has its own Dockerfile:

```text
docker/tests/Dockerfile.backend-mocked
docker/tests/Dockerfile.backend-integration
```

### Mocked backend suite

`Dockerfile.backend-mocked` validates the Core backend without external infrastructure. It uses an isolated SQLite database and executes the backend unit suite plus the deterministic OpenAI-compatible fake provider contract:

```text
tests/unit
tests/fakes/test_openai_provider.py
```

Legacy Billing tests under `tests/unit/test_billing` are excluded because they are not part of the current Core validation surface. The broader structural/contract suites (`tests/modules`, `tests/contract`, `tests/messaging`, `tests/editions`) are not part of the mocked runner.

The suite writes JUnit evidence to:

```text
.test-artifacts/backend-mocked.xml
```

### Backend integration suite

`Dockerfile.backend-integration` validates the Core backend against real integration infrastructure supplied by Compose:

```text
PostgreSQL + pgvector
RabbitMQ
Redis
```

Before the integration suite, the runner applies the real Alembic migration chain required by the test database. It then executes:

```text
tests/integration
```

Legacy `tests/integration/billing` is excluded because it is outside the current Core validation contract.

The suite writes JUnit evidence to:

```text
.test-artifacts/backend-integration.xml
```

The integration environment deliberately uses local storage. Browser runners and product Web/ChatSurface containers are not part of this backend-only test contract.

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

CI only adds lifecycle and evidence handling around that command: cleanup, Compose validation, failure logs, teardown and artifact upload. Frontend/E2E, container, security, release and production acceptance remain separate validation surfaces.

## Live Go CLI contract

Backend CI checks out `woobe-cli` at the immutable revision declared in
`.github/workflows/tests.yml`, builds a Linux binary with that revision embedded,
and mounts it at `/artifacts/woobe`. `WOOBE_REQUIRE_CLI_E2E=true` makes absence of
that binary a failure rather than a skipped test. The live contract starts the
API and workers inside the integration container and uses the Compose services
for persistence, messaging and deterministic model responses.

To run the same contract locally, build that CLI checkout into
`.test-artifacts/woobe` with the same `internal/cli.Commit` linker value. Then run:

```bash
WOOBE_REQUIRE_CLI_E2E=true docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

Without a compiled binary, the normal local command skips only the live CLI
contract; the backend unit and integration suites still execute. Redacted CLI
command metadata is written to `.test-artifacts/cli-contract-*.json`. Issued keys
are stored only in private temporary files and never included in those reports.
The CLI revision is pinned deliberately; update the workflow and test pin
together when changing the client contract.

The pinned client now covers body pagination for category list/history/audit and
Agent sessions. The live authority contract exercises --all with limit=1,
revision history ordering, category cursor traversal, built-in side projections,
audit traversal, a max-pages partial result and initial-marker remaining scope.
A successful single-page response must not claim complete collection evidence.
The Agent workflow creates two independent staging sessions, traverses them
with a run:read key constrained to the Agent and staging, and rejects production,
the default draft filter and an unknown Agent. Native CLI package smoke covers
cursor traversal separately on three runner OSes.

## Verifying CI before a backend change

Open a draft pull request targeting `master` from a focused branch based on the current master. Backend, acceptance, package-build, container and security workflows subscribe to the PR opened/synchronize events; draft status does not disable those workflows. The CLA check also evaluates draft PRs. The architecture Quality Gate is path-filtered and includes this test-topology document; the frontend workflow runs only when its declared frontend/runtime-client paths change.

Distinguish an instantiated workflow from a running or successful job. These workflows use self-hosted Linux X64 runners: `queued` confirms event dispatch but does not prove runner availability. Record the head SHA, run links and final job conclusions in the PR. A skipped, cancelled or failed job is not successful validation. Do not move the PR out of draft merely to make the normal validation jobs start.

Use the same canonical Compose command above for backend validation. Acceptance and container workflows remain separate, broader checks; their success does not establish contracts or permissions that have not been implemented and tested. Workflow artifacts are conditional on `WOOBE_UPLOAD_CI_ARTIFACTS`; consult each workflow for whether evidence is uploaded on PRs or only manual dispatch. The workflow result and logs remain the primary initial CI evidence.

The request-validation pin adds live OpenAPI checks for UUID Project ownership
and Control Key expiration timestamps. Invalid inputs must return CLI exit 2
with no HTTP mutation/status and retain not_attempted evidence. Valid bodies
are checked read-only and then submitted through opt-in --validate-body. Native
package smoke independently exercises readOnly request direction; the backend
does not manufacture readOnly annotations in its DTOs to claim live coverage.

POST /core/projects explicitly advertises the validation schema from the same
CreateProjectInput DTO used by its transactional service. OpenAPI metadata does
not add a second DTO or change the existing authorization/dispatch ordering.

### DTO and parameter acceptance continuation

The required Go CLI tests additionally validate advertised provider credential,
provider model and Agent create schemas; Agent PATCH body/path; and Agent session
path/query pagination under the constrained reader. OpenAPI reference regression
tests verify all advertised DTO references resolve inside the real document.
Request metadata never bypasses the existing authorization/transaction boundary.

Local validation for the continuation: 285 API/Core/security/health tests passed;
all seven governed module architecture checks reported zero violations. Native
Go race/vet/module checks and packaged Linux smoke passed separately. Remote
workflow results must be associated with the exact new backend/client SHAs;
previous approved commits do not qualify the new head automatically.

The required CLI category workflow now imports a Workspace category definition
through manifest preflight/apply, resumes its private checkpoint without another
create, compares immutable revisions, captures selected fields with ETag and skips
an unchanged reordered permission set without bumping the revision. The already
issued reader key must stay pinned to the original revision and refuse writing.
Agent publication/rollback requires advertised body/path validation; MCP
permission preflight accepts `review` and refuses an unsupported mode without
performing Tool execution. These scenarios are enforced by the pinned client in
`tests/integration/cli/test_control_plane_workflow.py`; unit-schema fixtures do not
substitute for a successful required live run.
