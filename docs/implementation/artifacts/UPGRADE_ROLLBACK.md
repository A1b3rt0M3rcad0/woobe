# Upgrade and rollback

## Upgrade order

1. Back up PostgreSQL and the matching Artifact object namespace at one
   coordinated checkpoint. Keep the backup isolated from the live storage
   prefix.
2. Run the additive Alembic upgrade to `head` before starting binaries that
   advertise Artifact Workspace support. Confirm the database head in the
   startup capability report.
3. Deploy API and workers with document capabilities disabled unless their
   optional dependencies and writable scratch/storage configuration are
   installed. Enable Artifact routes only after the database and storage
   checks pass.
4. Enable policies for selected Projects/Environments, then validate old
   text-only Runs, existing Releases, new Artifact requests and revocation.

Migrations add nullable/defaulted columns and tables or extend constrained
values. Existing Sessions and Releases are not backfilled with Workspaces. The
runtime resolves logical bindings during Acceptance and persists a snapshot
only for the newly accepted Run/Session.

## Roll back application code

Turn off Artifact feature flags and stop new Artifact writes first. Preserve
the database schema, event ledger, object bytes and Artifact worker state. Roll
API, worker and client binaries back together to the last compatible release;
legacy text-only routes and Runs remain available. Keep new binaries gated
when the database capability is absent; never turn an Artifact reference into
text as a fallback.

Do **not** run Alembic downgrade as an application rollback. In particular,
0124 adds lifecycle fields that record deletion and purge; dropping
`content_state`, archive timestamps or tombstone state would erase recovery
evidence. Later Artifact migrations also hold durable receipts and source
lineage. Database rollback requires restoring the coordinated database and
object checkpoint in an isolated environment, then following
[`BACKUP_RESTORE.md`](BACKUP_RESTORE.md), including newer deletion tombstones.

## Re-enable

Re-run migration-head, storage-version, capability and worker-queue checks.
Reconcile any uncertain uploads or processing jobs before enabling writes.
Revalidate grants and rotate credentials after restore; a historical grant is
not proof of current authorization. Run exact-revision read, search isolation,
legacy text streaming and Release compatibility checks before restoring the
feature flag.

The tests in `tests/integration/artifacts/` create disposable PostgreSQL
databases, upgrade both a fresh schema and a project-bearing schema from the
pre-Artifact migration, re-run `upgrade head`, and drop the database afterward.
Those tests validate migration compatibility; they are not a production
rollback or recovery rehearsal.
