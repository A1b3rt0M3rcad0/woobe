# Upgrading Woobe Core

Woobe Core uses the root `compose.yaml` as its supported self-host topology.

## CI compatibility gate

Pull requests are validated against the most recent published platform tag reachable from the target branch. The Acceptance workflow initializes PostgreSQL with the previous release API image, preserves a persisted workspace probe, applies the PR's current migration image, runs Alembic consistency checks and confirms the persisted probe survives the upgrade.

This gate complements fresh-install migration tests. A green upgrade check means the tested previous-release schema can transition to the PR schema for that exact commit; release-specific migration notes are still required when operator action is necessary.

## Before upgrading

1. Read the release notes and migration compatibility notes for the target version.
2. Back up PostgreSQL using the documented backup procedure.
3. Back up Knowledge files or configured object-storage data.
4. Record the currently deployed source/image version and `.env`.

Do not assume that rolling an application version back also makes a database downgrade safe.

## Context Manager selections from older Agents and Releases

The name-only Context Manager contract reads the historical `context_assembler`
selection (also accepted under `context_manager`) containing `name`, `version`,
`strategy_name` and `strategy_version`. Known `stdcm:v1` and `stdcm:v2` identities,
including their `default` aliases, resolve to today's consolidated `stdcm`.
This upgrades the selection format; it does not preserve the old implementation's
exact behavior. In particular, current `stdcm` includes Skills and compaction.

Saving an Agent or creating a new Release writes only
`"context_manager": {"name": "stdcm"}`. Existing immutable Releases and Run
snapshots are interpreted without rewriting their stored configuration. Unknown
versions, custom legacy strategies, incomplete strategy identities and conflicting
selections remain errors rather than silently falling back to the current default.
`WOOBE_DEFAULT_CONTEXT_MANAGER` continues to require a plain registered name.


## Migration from the legacy ProjectRAI deployment contract

Treat an installation that still uses legacy `PROJECTRAI_*` configuration or historical Compose files as a deployment migration, not as a blind in-place restart.

Application settings previously named `PROJECTRAI_*` are now named `WOOBE_*`. Preserve existing signing/encryption keys and deliberately migrate service endpoints to the current topology.

## Source-based upgrade

```bash
docker compose build
docker compose run --rm migrate
docker compose up -d api workers web chat-embed
```

Verify API readiness, Web UI, ChatSurface, Workers, representative Agent/Network execution and Knowledge document access.

When `VITE_*` public configuration changes, rebuilding Web is mandatory because those values are build-time configuration.

## Rollback

Application rollback and Agent/Network Release rollback are different operations.

- Product Release rollback restores a previously published immutable Agent or Network Release.
- Platform deployment rollback restores a previous Woobe application artifact/source version.

Do not automatically execute `alembic downgrade` merely because an application artifact is rolled back. Use release-specific schema compatibility notes and a tested backup/restore path.

### ASaC retained artifacts and isolated Drafts

Migrations `0082` and `0083` add Package retained artifacts and Agent/Network
isolated Draft, revision, resource identity and operation tables. Existing native
Drafts/releases/selections are not rewritten. The default isolated Draft is
created lazily and marked `unknown_origin` until explicitly captured. Retained
artifacts must remain available independently of temporary upload expiration;
future storage cleanup must preserve references from ASaC records. Do not run
these migrations' destructive downgrades on a database whose new ASaC history
must be preserved. Lifecycle callers must negotiate the advertised capability;
isolated object storage alone does not provide publication or deployment fencing.

### Workflow reservations

Apply migration `0092` before using ASaC workflow leases. It adds durable owner
lease counters, database-clock deadlines and deferred authoring guards. Counters
cannot be reset or deleted while their native resource exists. The downgrade
refuses retained lease/operation evidence; do not rewrite applied migrations.
Active authoring reservations also gate legacy native writes. Use isolated Draft
proofs or explicitly release the owned reservation before a legacy edit.

ASaC exact Release selection adds migrations 0093–0094. Upgrade before using the
CLI deployment-plan workflow. Migration 0094 compares existing JSON operation
receipts to JSONB outbox evidence without changing retained records. Independent
selection authority cannot be downgraded by reverting migrations; recovery requires
an explicit forward migration preserving receipts and generations.

After an environment's first ASaC selection, legacy status/pointer writes are
rejected for that environment. Use a new exact plan with current generation,
current qualification and an owned environment lease. Agent Releases remain
immutable and can be selected independently by both Staging and Production.

### ASaC Project lifecycle policy (0095–0096)

Apply both migrations before exposing Project lifecycle policy. Existing
Projects remain explicit legacy mode until an administrator enables managed
mode using expected policy generation zero and a stable operation UUID. Every
new accepted policy change increments generation; identical replay does not.
Changes invalidate existing deployment plans. Policy changes require
`project:access:write`; optional stable Production actors narrow existing
permissions and never grant them.

Managed mode blocks legacy promotion, including Web and Package writes that
would create an unqualified immutable Release or bypass fenced environment
selection. Keep existing runtime keys and in-flight Runs; enabling the policy
does not rewrite existing executable snapshots. Deployers must use exact
Candidate evaluation/publication and deployment plans/leases. Do not silently
disable managed mode to make an old client work.

0096 permits normal outbox delivery fields to change while preserving policy
receipt/event content. Policy audit is append-only and generation cannot reset.
These migrations deliberately refuse downgrades that would remove authority;
use an explicit audited policy change or a reviewed forward migration.

Migration `0097` checks the captured Project lifecycle policy again at deferred
deployment commit. A changed policy generation or managed mode rejects the
transaction, and managed Production also checks the stable actor allowlist.
Apply migrations before serving traffic; this guard does not grant permissions.
