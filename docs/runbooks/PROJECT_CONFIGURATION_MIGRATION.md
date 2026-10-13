# Project configuration migration

The current administrative job covers Provider credential sources. Other source
families still require their own migration adapters; completing this job is not
evidence that an entire Project is ready for storage contraction.

Apply schema migrations before starting the bridge API and Workers. Keep a
consistent backup and an inventory of every API replica and Worker. Drain and
remove pre-bridge binaries before moving any source. The registry cannot detect
an old binary that never registered; a list of currently registered processes
does not prove the deployment inventory is complete.

Bridge processes advertise a unique boot identity every 30 seconds with a
90-second expiry. Graceful shutdown retires that identity. Heartbeat failure
expires the advertisement, blocking subsequent cutover batches. List live
advertisements with `GET /core/projects/{project_id}/configuration/migration-processes`.
Compare every page against the deployment inventory, including Workers. A restart
changes the identity: review the new inventory before resuming a batch.

The following routes require `project:environment:migrate` in all three
Environments. Reading/planning also requires `provider:read`; advancing requires
`provider:write`. These checks run again in the database transaction. Reports
contain identifiers, revisions, destinations and bounded diagnostics, never
credential material or its hash.

1. Preview with `POST /core/projects/{project_id}/configuration/migrations/preview`
   and `{"limit":100}`. Follow `next_after` using `after_id` for another page.
   Preview reads metadata only and changes nothing.
2. Choose a request UUID and persist that page with
   `PUT /core/projects/{project_id}/configuration/migrations/{migration_id}` and
   the same body. Repeating the same UUID, actor and pagination request recovers
   the existing plan. Changed parameters are rejected.
3. Inspect the plan with `GET` on that URL. The progress report supports `offset`
   and `limit`; its `next_after` selects the next inventory page, not the next
   progress page.
4. Advance with `POST .../migrations/{migration_id}/advance`:

   ```json
   {
     "expected_revision": 1,
     "required_processes": ["api:HOST:PID:BOOT_UUID", "worker:HOST:PID:BOOT_UUID"],
     "old_processes_drained": true,
     "limit": 10
   }
   ```

   `old_processes_drained` is the operator's explicit attestation, not automatic
   detection. Empty, absent, expired or incompatible process inventories block
   cutover. Registered live incompatible processes cannot be omitted to bypass
   the barrier. No batch schedules another batch automatically.
5. Stop sending batches to pause between commits, or send `pause:true` with the
   current revision to record the pause. Resume with `pause:false` and the new
   revision. A lost response can be recovered with `GET` or an identical retry of
   the latest batch request; it does not rotate or copy material again.

Each source uses its captured revision. A concurrent rotation leaves that source
untouched and reports `CONFIG_REVISION_CONFLICT`; preview and plan again after
reviewing the change. Sources with missing/invalid material are visibly incomplete
even when storage ownership has transferred. Unsupported destinations remain
blocked without inventing wildcard authority. Successful sources are committed
with central material, explicit compatibility routes and source clearing in the
same transaction, preserving credential IDs and storage-only revision evidence.

Review legacy mappings in Project → Environments. Converting selected Environments
is a separate authorized action; migration does not copy one value into three
slots. After a split, the old rotation endpoint returns
`LEGACY_ENVIRONMENT_REQUIRED` rather than overwriting multiple Environments.

After cutover, roll back application binaries only to a compatible bridge version.
Do not restore old ciphertext columns: rotations may already have changed the
central source. A pre-bridge rollback requires coordinated downtime and a
consistent backup/restore procedure. Retained Runs continue using their accepted
value versions subject to revocation and retention. Historical backups and logs
are outside the live-source migration and need their own retention policy.
