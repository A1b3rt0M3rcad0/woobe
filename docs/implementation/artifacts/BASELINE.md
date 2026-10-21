# Artifact implementation baseline

Inspected on 2026-10-20 in the existing isolated cloud checkouts.

| Repository | Exact inspected HEAD | Role |
| --- | --- | --- |
| A1b3rt0M3rcad0/woobe | 3dbcb3e1a7559f4a50ebca320e411933d46e8012 | Canonical implementation base |
| A1b3rt0M3rcad0/woobe-cli | e1fc3f3c7398a8b622ad1e1cf2acd4f1be117542 | Step 02 snapshot source |
| A1b3rt0M3rcad0/woobe-sdk-go | 5a78817a64dc5dcb15aa1d38ec54d4c289f7f56c | Step 02 snapshot source |
| A1b3rt0M3rcad0/woobe-sdk | 70265537d2ac3eddd2738c56d671b189794c5e5b | Step 02 Python snapshot source |

`git ls-remote origin refs/heads/master` confirms the canonical remote master
matches the inspected local base. The initial branch was `work`; no tracked
changes existed. The two untracked browser `node_modules` directories were
created during environment onboarding and must not be committed or imported.
No reset, worktree, merge, or changes to the separate client repositories are
needed. The proposed feature branch did not exist remotely at inspection.

PR #219's read-only Git ref resolves to
`1a3f22c0e7ba04d3c18730e1c4ef83c6eade30d5`, matching the supplied plan. It has
not been fetched into this branch or modified. Its current API status and Draft
flag cannot be independently verified: GitHub API requests are blocked at CONNECT
with HTTP 403, before authentication. Do not infer API access from Git access or
request a replacement token until the network restriction is resolved.

## Ownership and reusable boundaries

| Surface | Existing owner / integration point |
| --- | --- |
| Artifact domain, ports, use cases | New `modules/artifacts` boundary; no existing module to migrate |
| Metadata/migrations | `packages/woobe-core/migrations`, Alembic head `0106` |
| Storage compatibility | Agent `application/interfaces/file_storage.py`, `infra/storage/{factory,local_file_storage,s3_file_storage}.py` |
| Authorization | Identity/Core authority, Core Runtime Keys and API guards; do not create separate users/credentials |
| Model capabilities | Agent `domain/model_spec.py` and provider adapters; declarations alone are not qualification |
| HTTP | `packages/woobe-api/src/woobe_api/http`, only through Core entrypoints |
| Workers | `woobe_workers/composition/registries.py`, module consumers, explicit background boundaries |
| Durable execution | PostgreSQL, existing outbox/inbox/UoW; RabbitMQ delivery, Redis recovery, MongoDB event journal |
| Browser clients | `woobe-runtime-client`, frontend features, independently built embed |
| Architecture | Generic policies under `tooling/quality-gate/src/quality_gate/architecture/policies` |

The observed baseline matches the plan's Core/API/Workers and client separation.
No Artifacts implementation or generic public job implementation is claimed.
Existing package artifact storage is package distribution, not an ArtifactWorkspace.
No Knowledge objects are to be reinterpreted as fictitious Collections.

## Toolchain and external requirements

Current native tooling: managed Python 3.14.8 (Core), Python 3.13.16 (SDK), verified
Go 1.27.1, Node/npm, Docker/Compose. Python uses the frozen root uv lock; browser
packages use `npm ci`. Heavy optional document dependencies are not installed as
mandatory Core dependencies. Their versions, licenses and profiles must be fixed
and validated in their respective steps rather than guessed now.

GitHub Git reads work through the existing platform proxy. `api.github.com` needs
network access for PR creation/status. Alpine's `dl-cdn.alpinelinux.org` is blocked
for the full image build. Both additions have been saved in the environment draft;
that save does not establish active runtime connectivity. No secret is missing
based on evidence so far; GitHub API authentication is still untested after CONNECT.

Real S3/multipart, OCR/Docling/PageIndex, vision and image-generation providers need
their own qualification during the relevant steps. Use environment settings for
any credentials; do not embed credentials in source, logs or the execution ledger.

## Baseline validation evidence

These commands executed against the exact unmodified baseline during onboarding
in this same cloud machine. Logs remain under `/workspace/.onboarding`; they are
local evidence, not a claim of successful remote CI or portable published artifacts.

| Check | Actual outcome |
| --- | --- |
| Core native mocked selection, `WOOBE_RUN_PERSISTENCE_MODE=legacy_finalization WOOBE_DATABASE_URL=sqlite+aiosqlite:////workspace/.onboarding/mocked.db .venv/bin/python -m pytest -q tests/unit tests/fakes/test_openai_provider.py` | passed: 3118 tests, 10 subtests; 6 warnings |
| Frontend, `VITE_API_URL=http://localhost:8000 VITE_CHAT_EMBED_URL=http://localhost:8081 npm run test:run` | passed: 679 tests, 114 files |
| Frontend `npm run build` | passed; original tracked tsbuildinfo preserved/restored |
| Embed `npm run build`, `npm run typecheck`, `npm test` | passed: 25 tests |
| Python SDK pytest, Ruff, build and Twine metadata | passed: 34 tests; wheel and sdist metadata passed |
| Go SDK `go test -race -p 2 ./...` | passed: root and SSE test packages; example has no tests |
| CLI `go mod verify`, `make build`, `go test -race -p 3 ./...` | passed; real binary version/help also exercised |
| PostgreSQL migration to `0106`, repeated migration | passed against real PostgreSQL/pgvector |
| API `/health`, `/ready`, `/openapi.json`, worker health, browser assets | passed; 334 API paths; all four infrastructure containers healthy |
| Full product Compose image build | failed during setup: Alpine network/DNS unavailable; no product defect established |
| Canonical `compose.test.yaml` integration suite | not_run; native mocked validation is not integration qualification |
| Browser E2E, cross-platform packaging, live model/provider processing | not_run |

Initial native test runs lacked documented test settings: Core reported 8 failures
with `event_journal` and no Redis setting; browser tests lacked the absolute Vite
API/ChatSurface URLs. Re-running with the documented test environment produced
the passing results above without source changes. These are resolved setup errors,
not preexisting product defects.

Subsequent step 01 observation: after saving the required network additions, the
existing platform authentication successfully pushed the feature branch and
created PR #220. Its API reports OPEN, Draft, no auto-merge. No token was added.
The initial API failure above is historical, not an outstanding blocker.
