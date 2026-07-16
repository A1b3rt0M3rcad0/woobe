# Agent Release Lifecycle Plan

Branch: `feature/agent-release-lifecycle-v0`
Base: `development-mvp`

## Objective

Implement a complete agent lifecycle for draft, staging and production releases, including automatic system-owned version generation and playground support.

## Current state observed

The `development-mvp` branch already has:

- `agent.agent_releases` table represented by `AgentReleaseModel`.
- `ReleaseStatus` with `draft`, `staging`, `production`, `archived`, `rolled_back`.
- A partial unique index for one `production` release per agent.
- Runtime production resolution through `AskInput.execution_context == "production"`.
- Runtime support for `loaded_release_id` and `snapshot_override`.
- Release endpoints for create, list, get, promote and rollback.

Main gap: lifecycle semantics are incomplete. Promotion currently means production deployment only; staging is not resolved by runtime; draft/staging singleton constraints are not enforced; release version is user-provided instead of system-calculated.

## Versioning contract

Version format:

```text
v{compatibility}.{feature}.{YYYYMMDD}.{daily_sequence}
```

Example:

```text
v0.0.20260620.00
v0.0.20260620.01
v0.1.20260620.00
v1.0.20260621.00
```

Semantics:

- `compatibility`: incremented by breaking contract/runtime compatibility changes.
- `feature`: incremented by meaningful new product capability or feature set.
- `YYYYMMDD`: release creation date in UTC.
- `daily_sequence`: zero-based counter for the same agent, compatibility, feature and date.

Rules:

- Users do not provide the final release version.
- The backend calculates the version at release creation time.
- Legacy invalid versions are ignored for calculation but preserved historically.
- The system requires the caller to classify the change as `compatibility`, `feature`, or `change`.
- For MVP, classification can be explicit in the UI. Later it can be inferred from structured diffs.

Initial implementation committed:

- `src/modules/agent/domain/release_versioning.py`
- `tests/unit/agent/test_release_versioning.py`

## Target lifecycle

### Draft

- Exactly one draft per agent.
- Editable.
- Playground-only by default.
- Can be updated from current editor state.
- Can load an existing release snapshot.
- Cannot be invoked by public runtime unless explicitly using playground context.

### Staging

- Exactly one staging release per agent.
- Runtime/API accessible when `execution_context = "staging"` or equivalent environment selector resolves to staging.
- Can be created from draft.
- Can be replaced by loading an existing release.
- Used for pre-production validation.

### Production

- Exactly one production release per agent.
- Runtime/API accessible when `execution_context = "production"`.
- Represents the release currently deployed.
- Previous production release becomes archived or rolled_back depending on operation.

### Historical releases

- Multiple releases may exist.
- A historical release can be loaded into draft.
- A historical release can be loaded into staging.
- A historical release can be deployed to production.
- Historical release snapshots must not be mutated by load/promote operations.

## Backend plan

### Phase 1 — Domain and schema

1. Keep `AgentReleaseModel`; do not introduce a new deployment table for MVP.
2. Add partial unique indexes:

```sql
unique(agent_id) where status = 'draft'
unique(agent_id) where status = 'staging'
unique(agent_id) where status = 'production'
```

3. Add migration for the new unique indexes.
4. Decide migration behavior for duplicated historical drafts/stagings:
   - keep latest as `draft`/`staging`;
   - move older rows to `archived`.

### Phase 2 — Repository contract

Add repository methods:

```python
get_active_draft(agent_id)
get_active_staging(agent_id)
list_versions(agent_id)
replace_singleton_status(agent_id, release, status)
```

The implementation must update existing release with the target status to `archived` before assigning the target status to a new row, all inside the same transaction.

### Phase 3 — Automatic versioning integration

1. Change `CreateReleaseInput.version` from required to optional/internal.
2. Add `change_kind: compatibility | feature | change`.
3. `CreateReleaseUseCase` must:
   - fetch existing release versions for the agent;
   - calculate the next version using `calculate_next_release_version`;
   - persist the release with the generated version;
   - return the generated version.

### Phase 4 — Explicit lifecycle use cases

Add or split use cases:

```text
UpsertDraftReleaseUseCase
PromoteDraftToStagingUseCase
LoadReleaseToDraftUseCase
LoadReleaseToStagingUseCase
DeployReleaseToProductionUseCase
RollbackProductionReleaseUseCase
```

Keep existing `PromoteReleaseUseCase` temporarily as backward-compatible alias to `DeployReleaseToProductionUseCase`.

### Phase 5 — Runtime resolver

Update `AskAgentUseCase._load_agent`:

```python
if execution_context == "production":
    release = release_repo.get_active_production(agent.id)
elif execution_context == "staging":
    release = release_repo.get_active_staging(agent.id)
elif execution_context == "playground":
    release = loaded_release_id or draft or snapshot_override
```

Precedence for playground:

```text
snapshot_override > loaded_release_id > active draft > base agent
```

Precedence for staging/production:

```text
explicit environment target only; no silent fallback to draft
```

Failure behavior:

- `production` without production release: error.
- `staging` without staging release: error.
- `playground` without draft: use base agent or editor snapshot.

### Phase 6 — API endpoints

Add explicit endpoints:

```text
GET  /ai/agents/{agent_id}/draft
PUT  /ai/agents/{agent_id}/draft
POST /ai/agents/{agent_id}/draft/load-release/{release_id}
POST /ai/agents/{agent_id}/staging/promote-from-draft
POST /ai/agents/{agent_id}/staging/load-release/{release_id}
POST /ai/agents/{agent_id}/releases/{release_id}/deploy-production
```

Keep current:

```text
POST /ai/agents/{agent_id}/releases/{release_id}/promote
```

as alias to production deployment during transition.

## Frontend plan

### Playground UI

Add release lifecycle controls to the playground/editor:

- Current draft status.
- Save draft.
- Promote draft to staging.
- Load release into draft.
- Load release into staging.
- Deploy release to production.
- Clear visual distinction between draft, staging and production.

### Runtime target selector

Expose runtime target selector:

```text
Playground / Draft
Staging
Production
Specific release
```

Behavior:

- Playground execution uses draft/snapshot override.
- Staging execution sends `execution_context=staging`.
- Production execution sends `execution_context=production`.
- Specific release sends `loaded_release_id` only for playground/test mode unless explicitly allowed.

### Release list

Show release table:

- version
- status
- generated date
- model/provider
- risk score
- promoted_at
- actions

Actions:

- load to draft
- load to staging
- deploy production
- rollback when applicable

## Test plan

### Backend unit tests

- version parser accepts `v0.0.20260620.00`.
- first release is `v0.0.DATE.00`.
- same-day change increments sequence.
- feature change increments feature and resets sequence.
- compatibility change increments compatibility and resets feature.
- invalid legacy versions do not block generation.

### Backend integration tests

- only one draft per agent.
- only one staging per agent.
- only one production per agent.
- load release to draft does not mutate source release.
- load release to staging does not mutate source release.
- deploy production archives or rolls back previous production.
- runtime staging resolves staging release.
- runtime production resolves production release.
- runtime production does not fallback to staging/draft.

### Frontend tests

- release actions are rendered with correct enable/disable states.
- saving draft calls draft endpoint.
- promote to staging calls staging endpoint.
- deploy production calls production endpoint.
- runtime target selector sends expected payload.
- release list displays generated version.

### E2E/manual validation path

1. Create/update draft in playground.
2. Run playground test.
3. Promote draft to staging.
4. Run API/runtime call with staging environment.
5. Create/deploy production release.
6. Run API/runtime call with production environment.
7. Load old release into draft.
8. Edit and promote again.

## Expected result

After implementation:

- The user never types release version manually.
- Draft/staging/production uniqueness is enforced by database and use case logic.
- Runtime uses the environment requested by the caller.
- Production uses the currently deployed release.
- Staging can be tested through API/runtime before production.
- Playground stays isolated from production by default.
- Historical releases remain immutable and can be reloaded into draft or staging.
