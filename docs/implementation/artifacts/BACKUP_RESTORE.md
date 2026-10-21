# Artifact export, retention and recovery

## Authorized logical export

`GET /v1/artifact-workspaces/{workspace_id}/export-manifest` returns a private
NDJSON stream for the Workspace's visible catalog snapshot. The first record
pins `catalog_version`. File records identify the exact `artifact_id` and
`revision_id`, original path, content type, byte count and SHA-256. Ready
representation sets and visible derivative entries carry their generation,
recipe/processing fingerprints and individual hashes. A ready document index is
identified by its engine/version and manifest hash. No storage key or credential
is returned.

Each content record has a separate authenticated `content_url`. Fetch original
and derivative bytes through those existing bounded streaming routes, verify
the downloaded size and SHA-256, and retain the original manifest bytes. The
last record contains a SHA-256 of every preceding NDJSON line and the record
count. An export without a valid `end` record is incomplete. This protocol does
not package content into a ZIP or buffer a Workspace in the API process.

The logical export contains current visible file heads and their authorized
published representations/indexes. It is suitable for application-level
transfer. It does not claim to preserve all historical revisions, upload
receipts, Run records, authorization grants or private operation metadata.

## Full backup and restore

For a full historical recovery point, back up the Artifacts PostgreSQL schema
and the matching storage namespace together. Preserve S3 object versioning and
the object version IDs recorded by Artifacts. For local storage, snapshot the
shared `UPLOAD_LOCAL_DIR/artifacts` tree together with the database checkpoint.
Do not copy an actively changing database and object tree as unrelated snapshots;
quiesce writes or use a coordinated database/object-store snapshot procedure
provided by the deployment platform.

Restore into an isolated database and storage prefix first. Keep API and worker
traffic disabled while reconciling the restored state against the latest
authoritative lifecycle records from the source environment. Reapply every later
`artifact.revision.purged` and `artifact.workspace.purged` tombstone before
enabling reads. Reconcile object keys by exact key and version; missing objects
must stay unavailable, and retained revisions must pass their stored hash checks.
Do not restore grants from an older snapshot as active credentials; rotate or
revalidate them with the current authority before serving traffic.

The restore helper takes Workspace IDs from the authoritative source event ledger
after the restored database checkpoint. Including a revision-purge event fences
its whole Workspace in the restored copy; this conservative rule handles a
snapshot where that revision was still the current head. Example source query:

```sql
SELECT DISTINCT workspace_id
FROM artifacts.events
WHERE kind IN ('artifact.revision.purged', 'artifact.workspace.purged')
  AND created_at > TIMESTAMPTZ '2026-10-21 00:00:00+00';
```

Place the resulting IDs in an operator-controlled JSON file and run this only
against the isolated restore target:

```json
{"source_checkpoint":"backup-2026-10-21T00:00Z","workspace_ids":["workspace-id"]}
```

```sh
WOOBE_DATABASE_URL='postgresql+asyncpg://...' \
  .venv/bin/python scripts/reconcile_artifact_restore.py /secure/restore-tombstones.json
```

The command puts those Workspaces into `deletion_pending`; keep the API offline
until the lifecycle worker has deleted their stored objects and recorded
`artifact.workspace.purged` in the restored database.

The reconciliation source must survive the snapshot being restored. If the live
database and every independent tombstone/WAL archive are lost, an older backup
cannot prove which later deletions occurred. Do not serve such a restore until
the deletion ledger is recovered; a backup cannot revoke copies already exported
outside Woobe's control.

Recommended restore checks are: compare revision and representation hashes,
confirm all ready indexes reference present source maps, verify quota counters,
run the Artifacts isolation suite, and exercise exact-revision reads before
re-enabling workers. Keep the restored service isolated if any reconciliation or
integrity check fails.

## Retention worker and object-store permissions

The existing `woobe-workers` process runs the bounded lifecycle poller. Archive
retention transitions a Workspace to `deletion_pending`; the grace period then
allows queued processing to be cancelled and running/uncertain work and active
uploads to settle. Reads and writes are denied while deletion is pending. The
worker marks stale revisions unavailable before deleting their original and
derived objects, then clears searchable text and releases quota only after
storage cleanup succeeds. Storage failures leave durable references for a later
retry. Workspace purge is idempotent and ends by scrubbing source lineage and
revoking Workspace-specific grants.

The S3-compatible role needs object read/write/delete permissions and, for
versioned buckets, `ListBucketVersions` plus `DeleteObjectVersion` scoped to the
configured Artifacts prefix. Purge removes every version and delete marker for
the exact immutable object key when no version ID is available. Provider-side
replicas, lifecycle copies, backups and exports remain under their respective
operators' retention policies.

Useful checks:

```sh
docker compose -f compose.yaml -f compose.artifacts-documents.yaml config --quiet
docker compose -f compose.yaml -f compose.artifacts-pageindex.yaml config --quiet
PYTHONPATH=.:packages/woobe-core/src:packages/woobe-api/src:packages/woobe-workers/src \
  .venv/bin/python /workspace/.onboarding/run_artifact_tests.py -q \
  tests/integration/artifacts/test_lifecycle_postgres.py
```
