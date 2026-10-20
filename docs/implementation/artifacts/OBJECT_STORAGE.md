# Shared object storage contract

`shared.contracts.object_storage` defines streaming put/open/stat/delete, SHA-256
metadata, explicit half-open byte ranges and safe typed storage errors. It contains
no Collection, Agent, HTTP or vendor SDK types. `read_bounded` closes its stream on
success, overflow and early termination. Adapters own resource closure; raw object
keys are internal server references, never an Agent-provided host path.

The shared local adapter operates on descriptor-relative paths, rejects traversal
and symlink/special-file reads and streams bytes in bounded chunks through worker
threads. Metadata is separate from the original content and checked against real
size/hash. Old Knowledge files without sidecar metadata remain readable; their
existing database metadata is not migrated or reinterpreted.

Agent LocalFileStorage is a compatibility facade preserving save_document,
read_document, read_document_bounded, delete, original key construction, filename
sanitization, hashes and explicit legacy replacement. Knowledge identities do not
enter the generic port. Artifacts imports the same shared contract rather than
Agent infrastructure. S3 Knowledge behavior is preserved; its streaming generic
adapter is delivered in the dedicated S3 step.

The local-storage step adds private unique staging, incremental hash/size checks,
flush/fsync and atomic promotion after closing the verified handle. Immutable
publication uses an exclusive link and removes its temporary name under a cooperative
directory publication lock; readers take a shared directory lock while opening and
validating the file so they cannot observe the temporary two-link state. Explicit legacy
replacement uses atomic replace. Identical retries reconcile verified original
bytes and repair a lost metadata ACK; different bytes/metadata cannot overwrite an
immutable object. Failed writes never remove a previously published original.

Cancellation waits for owned threaded OS work before closing/reusing descriptors.
Incomplete staging is not addressable through the public port. Staging cleanup
requires a grace period, rejects unreadable traversal, never follows symlinks and
skips locked files still being written. A real terminated writer leaves only
unpublished staging that is eligible for cleanup. Final verified objects awaiting
catalog publication are reconciled by the later lifecycle step, not blindly erased.

Artifacts derives physical keys solely from Project/Environment/Workspace/Artifact/
revision IDs. Logical filenames, including Unicode names, never become host paths.
Private metadata/staging paths and nonportable physical names are rejected; the
Knowledge facade explicitly retains old portable-key behavior. Worker scratch is
private per operation and removed on context exit. Worker adapters invoke blocking
scratch/conversion operations within their worker-thread boundary.

Local object bytes and metadata must survive on a compatible shared volume when
API/Workers are replicated; independent ephemeral disks are unsupported. The
Artifacts composition root uses a dedicated `artifacts` subdirectory beneath the
configured upload root and refuses other storage drivers until their adapter is
wired. No public Artifacts upload is advertised yet. S3 qualification is separate.

Step 07 contract checks cover empty/small/large streams, persisted metadata after
adapter recreation, range reads, immutable identity, checksum failure, bounded and
early consumption, idempotent deletion and exact old Knowledge keys/bytes including
replacement. Existing portable-document filesystem/S3 bounded-read regressions
remain enabled. Full mocked Knowledge, package/export and runtime regressions run
without changing legacy data or Release behavior.

Step 08 additionally exercises slow staging visibility, cancellation during OS
resource acquisition, stream interruption, injected disk exhaustion, checksum
failure, immutable races, metadata ACK loss, descriptor-relative link/traversal
refusal, invalid Range, a real subprocess crash and locked/expired staging cleanup.
A generated 64 MiB stream measured under 8 MiB peak traced Python heap (the first
recorded run measured 148,894 bytes); this demonstrates absence of a full Python
upload buffer, not total RSS or production throughput. Measurements are local
adapter evidence, not S3 or multi-node qualification.
