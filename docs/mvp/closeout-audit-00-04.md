# MVP closeout audit — stages 00 through 04

Audit branch: `mvp-closeout-audit`  
Audit starting point: `30ddd69be9386d6c0730f9647f3caf7a6f561c55`  
Comparison base: `development-mvp`  
Audit date: 2026-06-19

The audit branch was created at the same commit as `development-mvp`. That commit already contains the stage 05 merge, so this report limits acceptance analysis to stages 00–04 while checking that the current integrated head did not remove their controls.

Status definitions:

- **Implemented**: implementation and current evidence satisfy the audited criterion.
- **Corrected**: a confirmed omission was fixed on this audit branch.
- **Evidence gap**: implementation exists, but the required acceptance test or historical evidence is absent.
- **Open blocker**: the current repository cannot honestly be represented as satisfying the criterion.

## Executive result

| Stage | Result | Main conclusion |
|---|---|---|
| 00 | Partial | The frontend and idempotency correction are present, but the original baseline report did not execute or preserve the required reproducibility evidence. |
| 01 | Partial / release blocker | CI workflows exist and run, but the backend gate was green with 152 failing tests hidden behind an allowlist. The allowlist drift was corrected; the failures remain. |
| 02 | Partial, corrected | Signed access tokens, hashed rotating refresh tokens, real current-user lookup and centralized tenant authorization exist. Rotation lineage (`replaced_by`) was missing and is now implemented. The complete cross-tenant endpoint matrix still lacks verified integration evidence. |
| 03 | Partial | Hashed scoped API keys, project-bound runtime authorization, payload limits, redaction, rate/concurrency controls and HTTP tool hardening exist. The mandatory isolation/SSRF integration matrix is not fully demonstrated by the stage changes. |
| 04 | Partial, corrected | Real provider streaming and SSE v1 exist. Confirmed UI omissions were fixed: stop control, supported-provider restriction and fresh credential selection. Cancellation persistence and the full fallback/tool/structured-output E2E matrix remain evidence gaps. |

## Stage 00 — frontend baseline

### Implemented

- The expected frontend routes and playground/dashboard surfaces are present in the integrated branch.
- The repeatable-mutation idempotency correction remains in `event_mappers.py`.
- `tests/modules/agent/test_repeatable_mutation_idempotency.py` protects distinct updates and deterministic replay behavior.

### Evidence gap

`docs/mvp/baseline-report.md` contains only the stage identifier, base SHA and an explanation that `development-frontend` was not used. `docs/mvp/baseline-evidence.md` explicitly records that build, test, migration and smoke evidence had not been executed. This does not meet the original requirement for versions, commands, outcomes, pre-existing failures and a critical route/screen inventory.

Historical execution cannot be reconstructed retroactively with the same evidentiary value. This audit therefore records the gap instead of marking the original gate complete.

## Stage 01 — CI and quality gates

### Implemented

- Separate backend, frontend, migration and container workflows exist.
- Frontend uses `npm ci`, build and Vitest.
- Migrations require one Alembic head, upgrade an empty PostgreSQL/pgvector database and run `alembic check`.
- The latest integrated pre-audit head passed the four principal GitHub Actions workflows.

### Confirmed defect

The backend workflow did not require a passing pytest suite. It accepted a hash allowlist hardcoded to 178 reviewed failures. The latest JUnit artifact contained:

- 3,342 passing tests;
- 152 failing tests;
- 8 skipped tests;
- 26 allowlist entries that were already resolved but still accepted.

A green backend check therefore meant only “no unreviewed failure hash”, not “backend tests pass”. This conflicts with the plan rule against masking failing tests.

### Correction

- The allowlist was reduced from 178 to the 152 failures actually present in the latest artifact.
- `run_pytest_baseline.py` now requires an exact set: new failures fail, stale/resolved hashes also fail, and the allowlist may only shrink.
- Documentation now states explicitly that this gate tracks reviewed debt and is not a green full-suite claim.

### Open blocker

The 152 failures still exist. Before release hardening can claim a passing backend suite, the allowlist must reach zero and plain `pytest -q` must pass. Pyright is also limited to changed production files; a complete repository type-check remains unproven.

## Stage 02 — authentication and tenancy

### Implemented

- Access tokens are signed HS256 JWTs with `sub`, `sid`, `type`, `iat`, `nbf`, `exp`, `iss` and `aud` validation.
- Refresh secrets are opaque and stored as hashes.
- Login, registration, refresh and logout use a centralized authentication service.
- `/identity/users/me` resolves the authenticated user.
- Organization listing is membership-scoped.
- A global HTTP security dependency produces authenticated principals and invokes `TenantAuthorizer` for organization, project and mapped resource identifiers.
- Revoked/expired sessions are rejected server-side.

### Confirmed defect and correction

The plan required refresh-session lineage with `replaced_by`. The previous model revoked the old session and issued a replacement but stored no link.

The audit adds:

- migration `0029_link_rotated_user_sessions.py`;
- nullable self-reference `replaced_by_session_id` with index and `ON DELETE SET NULL`;
- assignment of the replacement session during rotation;
- a unit test proving the old session is revoked and linked to the new session.

### Evidence gap / residual risk

- The stage 02 PR did not add the required comprehensive tenant A versus tenant B test matrix for projects, agents, credentials, tools, knowledge, sessions and traces. Centralized authorization is present, but endpoint-by-endpoint isolation must still be demonstrated against PostgreSQL.
- `refresh_cookie_secure` defaults to `false`. That is appropriate for local development but production configuration validation must force secure cookies during the deployment stage.
- Login and API-key limits are process-local; horizontal deployment requires a shared limiter or an explicit operational constraint.

## Stage 03 — API keys and runtime security

### Implemented

- Project keys use `rai_live_<public-prefix>_<secret>` with cryptographically random material.
- Only a digest and public prefix are stored; the complete key is returned only on creation.
- Runtime authentication derives the project from the API-key principal and applies server-side scopes.
- Revoked and expired keys are rejected.
- Runtime request, prompt, metadata, snapshot and total-duration limits are configured.
- Logs and nested sensitive data have redaction utilities.
- HTTP tools allow only HTTP/HTTPS, reject non-global destinations, disallow redirects, bound timeout/response size and close the shared client during shutdown.
- Unit coverage exists for key format, scope normalization, redaction and process-local rate/concurrency limits.

### Evidence gap / residual risk

The stage acceptance plan required integration tests for wrong-project execution, revoked/expired keys, missing scopes, runtime resource ownership and SSRF across localhost, RFC1918, link-local, private IPv6 and redirects. The current stage-specific test file does not cover that complete matrix. Those behaviors are visible in implementation, but implementation inspection is not acceptance evidence.

The HTTP executor performs DNS validation before the HTTP client resolves the host. This reduces common SSRF paths but does not cryptographically pin the validated address to the actual connection; DNS rebinding remains a hardening concern for the release/security stage.

## Stage 04 — playground streaming

### Implemented

- SSE protocol version 1 includes request metadata and typed events.
- The runtime uses the provider async stream and emits token chunks progressively.
- The stream channel measures TTFT and enforces exactly one terminal event.
- Trace/session identifiers are bound and `meta` is emitted before LLM execution.
- The controller includes heartbeat handling and cancellation paths.
- The frontend parser handles arbitrary byte chunks, final buffers, invalid JSON and unknown event types.
- Sessions and messages are reloaded from backend state.
- The editor keeps a separate baseline for dirty-state comparison.

### Confirmed defects and corrections

1. **No user cancellation control**: the stream could be aborted programmatically, but the chat composer exposed no stop action. A visible stop button now aborts the active request.
2. **Unsupported providers offered**: the credential modal still offered Anthropic and Google. New/runtime credential choices are now restricted to OpenAI and custom OpenAI-compatible providers.
3. **Stale credential selection**: after creating a credential, `ModelSettingsTab` awaited a refetch and then searched the pre-refetch render array. The credentials hook now preserves a stable refreshed collection, allowing the newly created credential to be selected from the returned data.
4. **Missing backend streaming invariants test**: tests now cover progressive token events, accumulated output, TTFT and exactly one terminal event.
5. **Stale progress record**: `stage-04-progress.md` no longer claims the merged implementation is merely in progress; it records completed corrections and remaining evidence.

### Evidence gap / open blocker

- Browser abort must be proven to propagate through the HTTP disconnect to the provider and persist a final `cancelled` trace/message state in a PostgreSQL integration or E2E test.
- Fallback sequencing, successful/failed tool calls and structured-output valid/repaired/invalid paths need stream-contract integration tests.
- Session/history recovery after reload needs an E2E provider mock.
- TTFT, total duration and provider/tool failure telemetry need acceptance assertions.

## Prioritized remaining work

### P0 — required before stating stages 00–04 are closed

1. Remove the remaining 152 pytest failures and delete the allowlist.
2. Add a PostgreSQL cross-tenant endpoint matrix covering all private resource families.
3. Add API-key integration tests for project isolation, revocation/expiry and scope denial.
4. Add cancellation persistence E2E and stream event-order tests for fallback, tools and structured output.
5. Re-run backend, frontend, migrations and containers on the final audit head.

### P1 — required before production release

1. Enforce secure refresh-cookie configuration outside development/test.
2. Resolve or formally constrain process-local rate/concurrency limiting for multi-worker deployment.
3. Strengthen HTTP tool DNS/connect binding against rebinding.
4. Run full-repository Pyright and reduce existing type debt.
5. Replace the incomplete historical baseline document with a current reproducible system inventory, clearly labeled as a closeout baseline rather than original stage-00 evidence.

## Merge recommendation

Do not represent this audit as proving full completion of stages 00–04. Merge is reasonable only as a corrective/audit PR if all current CI workflows pass and the PR description preserves the open blockers above. No promotion from `development-mvp` to `development` is authorized by this audit.
