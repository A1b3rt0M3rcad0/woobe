# Project configuration migration

The administrative job covers Provider credentials, recognized API-key/custom
Secrets referenced by global HTTP/MCP headers, and global Tool header literals
without retained snapshots. OAuth, route-local material and retained inline
snapshots still require their own adapters; completing this job is not evidence
that an entire Project is ready for storage contraction.

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
Environments. Reading/planning also requires `provider:read`, `secret:read` or `tool:read` for the selected
source family; advancing requires the corresponding `:write` permission. These checks run again in the database transaction. Reports
contain identifiers, revisions, destinations and bounded diagnostics, never
credential material or its hash.

1. Preview with `POST /core/projects/{project_id}/configuration/migrations/preview`
   and `{"limit":100}` (Providers), `{"source_kind":"secret","limit":100}`, or
   `{"source_kind":"tool","limit":100}`. Follow `next_after` using `after_id`
   for another page, including when the current page has no eligible sources.
   Preview changes nothing and returns metadata only. Inspecting old Tool source
   JSON reads the author definition internally; no material or material hashes
   enter the report, and no decryption or outbound request takes place.
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

### Shared legacy Secret authority

The central alias store can retain an explicit set of Tool/field consumers for one
legacy Secret. Trusted owner adapters capture that set during migration or an
explicitly authorized compatibility Tool write. The latter requires Secret read
and use-policy write authority for all compatibility Environments. Public
use-policy grants alone do not add consumers, and knowing a Secret name or alias
ID does not create authority. Existing revocations survive Tool edits.
Destination and Environment policy checks still apply at acceptance and send
time. An unknown alias is an error; it never falls back to an Environment value.

New Provider and Secret API writes already centralize material in their first
transaction. Inventory intentionally selects only pre-bridge source rows; an empty
Provider/Secret page is not evidence that inline Tool/OAuth sources migrated.

Secret cutover captures the current and retained Agent Tool header closure and
compares it again before moving material. Recognized header templates are compiled
only in runtime/readiness/discovery projections; author snapshots are not edited.
Rotation uses the central alias and preserves accepted Run versions. Ambiguous
rotation after an Environment split is rejected. Direct legacy resolution without
consumer/Environment identity is rejected. Deleting a migrated Secret identity
with retained references is rejected; manage material centrally.

Route-specific or mixed authentication, unsupported Secret types, and malformed
templates require explicit review. They stay blocked with their source untouched;
no route is broadened to make migration succeed. Package 2.0 structural exports
project migrated headers as destination configuration declarations, omitting local
alias authority and material. Package 1.0 retains its existing author projection.

Cutover acquires the Project barrier before source and migration rows. Agent
Acceptance (including legacy-only Runs), Network dependency reads, Package
Acceptance and vector preparation participate in this barrier. Provider updates
re-read the current source under that ordering so a concurrent legacy writer
cannot restore inline material after cutover.

`CONFIG_MIGRATION_WORK_PENDING` means that active or uncertain Runs, queued Network
work, vector builds, nonterminal Package operations or unconsumed, unexpired plans
must be resolved before retrying. The operator's fleet attestation does not bypass
these checks. A consumed terminal Package plan does not require waiting for its
expiry. The administrative job checks each owner's metadata through host-composed
ports; it does not query another domain's private persistence from Core.

### Newly supplied Tool header literals

HTTP/MCP creation and replacement of explicitly sensitive global header literals
now centralize that material atomically. The mutable Tool configuration contains
only its owner-checked compatibility reference. The initial grant is limited to
the supplied Tool, field and fixed destination. Replacing a literal rotates the
same central source and preserves policy revocations; retargeting needs a separate
authorized use policy. An Environment-split source rejects ambiguous old writes.

The `tool` migration adapter can backfill existing global header literals only
when the Tool has no retained Agent snapshot. It rechecks the source revision,
destination, retention and quiescence inside the cutover transaction. Retained
snapshots, OAuth state and route-local material report
`LEGACY_FORMAT_UNSUPPORTED`; they are never silently rewritten or treated as
completed. Route-specific material must preserve its route boundary and is never
promoted into a Tool-wide grant.
