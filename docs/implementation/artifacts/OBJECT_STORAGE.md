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

Step 09 adds the shared S3 adapter and the legacy Knowledge facade. Immutable
publication uses conditional multipart completion (or conditional empty-object
put), actual streamed SHA-256/size verification and reconciliation after a lost
completion response. ETag is never interpreted as a content checksum. Uploads
are bounded to four concurrent streams per adapter with sequential 8 MiB parts;
part size is configurable within 5–64 MiB and the 10,000-part ceiling is enforced.
The factory retains the existing boto3 credential chain, SigV4, TLS verification,
endpoint/region/path-style configuration and configured server-side encryption.
Credentials and multipart IDs remain server-side. Storage receipts contain only
key, verified metadata and an optional backend VersionId.

Range reads close their bodies on completion, interruption and early consumption.
A failed read is explicitly retryable from the caller's contracted offset, without
silently appending a restarted body. Cleanup lists only an owned prefix, requires
a grace period and checks the current owner's active state before aborting private
multipart uploads. No upload URL exists that could mutate a completed object.
Unsupported conditional-write endpoints fail closed. Artifacts composition now
supports configured local and S3 profiles; configuration membership alone does not
advertise readiness or a public upload capability.

The real compatibility suite uses SeaweedFS 4.48, upstream commit
`530be3e37337488ecc34d58441e0bc476e121c93`, under Apache-2.0. The optional development
helper `scripts/ci/artifact_s3_test_server.py` downloads its official Linux amd64
release and checks SHA-256
`4a7d108384d044d95212d1342cdda9533fa55842c1c9b41f606ca3c8a9561124`
before execution. The binary is external test infrastructure, never bundled in a
product artifact. Sources/license: https://github.com/seaweedfs/seaweedfs/tree/4.48.
Generated credentials and state stay outside the checkout, private and bound to
localhost. Startup validates authenticated S3 access; stop checks process ownership.
The read-only `artifacts-storage.yml` workflow repeats these real-service tests.

Qualification covers empty and 11 MiB multipart objects, SHA-256 metadata, Range,
immutable races, failed checksum/input/part, aborted staging, completion ACK loss,
safe read retry, active-owner expiry protection, bounded upload concurrency and
legacy keys/attributes/overwrite. This is local S3-compatible evidence. No real AWS
account, KMS integration, replicated production service or SSE behavior was tested;
these features are not claimed as qualified by this suite.

Stage 20 adds metadata-only head(key) to the internal streaming contract for
bounded proof-based SourceRef reads. It returns the declared immutable-write
receipt (and checks the local object's size) without claiming payload integrity.
S3 issues HeadObject without GetObject; local storage reads only safe file metadata
and the bounded private receipt. Strong stat retains full SHA-256 byte verification.
Readers authenticate selected independently hashed canonical text segments; see
[INDEXES.md](INDEXES.md). No signed/public storage URL or ETag-as-SHA substitution
is introduced.
