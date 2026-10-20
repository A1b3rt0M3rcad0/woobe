# Durable processing inside the existing Workers

Processing requests freeze source Artifact/revision, exact selected recipe, safe
principal snapshot and reuse fingerprint. Request and standard outbox event commit
together. Replaying an operation returns its original job, including after a
Workspace default changes; another payload conflicts. No raw access token, API key
or credential value is retained in the job or queue payload.

The existing WorkerRunner discovers ArtifactsWorkerRegistry. One poller owns a
bounded set of independent processing slots and uses the Worker process's engine
and lifecycle. There is no separate document daemon, generic Runtime Jobs interface
or new product scheduler. Like existing Ask/Vector Snapshot pollers, it operates
with RabbitMQ absent: short transactional local delivery moves the standard
outbox contract to the standard inbox contract, with unique message/idempotency
identity. Inbox acceptance is distinct from completing the job. This implementation
qualifies the durable PostgreSQL queue path, not a new RabbitMQ processing protocol.

Admission reserves bounded queue capacity under a Project advisory lock (default
1000 nonterminal jobs per Project, 100 per Workspace). Active leases separately
limit authorized concurrent work (default four per Project, two per Workspace).
Persisted Project/Workspace last-claim ordering prevents one old FIFO from being
drained before other tenants, even with a single process slot. SKIP LOCKED and
Project serialization prevent concurrent claims from exceeding those budgets.
Worker-local slots/lease duration belong to WorkerSettings; queue/Project/Workspace
budgets belong to shared product policy. Lease timestamps use the PostgreSQL clock.

Each claim has a stable job ID, separate attempt ID, monotonically increasing
fencing token, owner and expiry. Heartbeats extend only a current, live lease.
Before I/O and checkpoint/publication, the Worker revalidates live principal,
Workspace grants, source availability, pinned recipe readiness and fencing. Storage
I/O holds no database connection. Checkpoints have bounded metadata and immutable
per-stage contents; large derivative bytes belong in private object storage, not
unbounded job JSON. An expired owner cannot checkpoint, complete or replace a newer
owner's result. Attempts retry with backoff at most three times. Permanent access,
format or integrity failures do not loop indefinitely.

Queued cancellation is immediately confirmed because no Worker owns I/O. Running
cancellation is cancel_requested until the owner stops and closes its resources.
Lease expiry before an ACK becomes uncertain, not a false assertion that remote
work stopped. A matching final owner can reconcile the stopped operation to
cancelled; a stale different attempt cannot publish. Already succeeded receipts
remain succeeded when cancel or a lost completion ACK races them. Cancellation
means no future authorized publication; it does not undo already completed I/O or
external provider costs. In-flight work and orphan staging require the later
lifecycle/side-effect reconciliation where applicable.

This step runs real original size/SHA-256/MIME/backend-version verification in the
store_only pipeline. A succeeded store_only result explicitly says
processing_performed=false and has no representation/index. Converter/index
pipelines remain unavailable until their adapter steps are implemented and
qualified. The pipeline port declares ordered stages and a current-authorization callback.
The coordinator itself skips already committed stages, so an adapter is never
re-executed merely because its checkpoint ACK was lost. Adapters do not own the
checkpoint transaction or lease decision.

Direct HTTP POST /v1/artifacts/{artifact_id}/processing accepts an operation and
exact source revision. GET /processing/{job_id} and POST /processing/{job_id}/cancel
require the same scoped owner and current grants; a different source in the path
is rejected. Public job state excludes storage keys, actor snapshots and fencing
material. These routes use only the Artifacts interface and do not enable generic
Agent/Network Jobs or execute a Run.

Real PostgreSQL tests cover atomic request rollback, duplicate delivery, same-ID
conflicts, one-current-owner fencing, lease recovery, current authority revocation,
heartbeat cancellation, expiry uncertainty, finite admission/concurrency budgets
and single-slot Project/Workspace fairness. Local and real S3 adapters verify real
originals. Subprocesses actually terminate with os._exit before/after a committed
checkpoint; replacement Workers repeat only uncommitted verification. A lost
checkpoint ACK recovers the existing checkpoint, and a lost terminal ACK returns
the immutable result. A fault-injected extraction-stage fixture writes through real storage and proves
that the coordinator executes it once after a lost checkpoint ACK. That fixture
qualifies orchestration, not a document converter. Format-specific restart/golden
checks are added with the native converter; store-only does not claim extraction
qualification.
