# Resumable upload and durable publication

UploadService orchestrates independent short transactional handlers around storage
I/O. Each database phase checks the live principal and Workspace grant. The intent
belongs to its initiating principal; even another principal with full access to
the same Workspace cannot inspect, resume or confirm it. No transaction holds a
database connection while streaming parts or publishing the final object.

An intent fingerprints the complete versioned request and reserves expected bytes
under the Workspace row lock. Identical operation retries return the original
intent/receipt; another payload conflicts. Concurrent reservations cannot exceed
quota. Server-generated Artifact/revision IDs remain stable across interrupted
confirmations. Proxy transfer uses nonempty parts of at most 8 MiB, a maximum of
4096 parts and explicit offsets. Each immutable private part key includes its
server-owned intent, offset and actual digest. Only the same bytes at the same
offset can replay an accepted part. Offset advancement commits after verified
storage, so a disconnected caller can query status and safely resend.

Confirmation freezes the accepted part manifest, streams and hashes each part,
checks whole-file size/SHA-256 and validates declared media against known binary
signatures or a bounded UTF-8 prefix. This conservative sniff is not a malware
scanner, a complete format parser or processor readiness. Original bytes are never
changed. The final immutable key derives only from scope and server IDs. Local
and S3 storage verification precedes revision/history, quota conversion, durable
receipt and publication event in one transaction. Optional backend VersionId is
retained on the immutable revision. Events are durable outbox entries; worker
consumption is implemented in the processing step.

Two confirmations may verify the same deterministic original concurrently, but
only one catalog transaction publishes it. Lost storage or database ACKs reconcile
to the same revision/receipt. Expected-revision CAS prevents concurrent updates
from overwriting one another. A failed CAS retains its reservation until explicit
abort or expiry, allowing safe status/recovery. Expiry and abort release quota
once; a committed receipt remains committed when cancellation races it. An abort
winning while final bytes are being stored prevents catalog publication. Such
unreferenced immutable objects/parts remain private and require the later
lease-aware lifecycle reconciliation, not unsafe immediate deletion.

This version exposes proxy transfer only; it does not issue signed URLs or expose
storage keys/credentials in UploadView. No staging URL can overwrite a completed
original. Upload maximum follows the existing configured upload_max_mb (default
25 MiB, configuration ceiling 512 MiB), independently of adapter maximums. A
receipt acknowledges catalog publication, not extraction/index completion.

The real PostgreSQL suite runs both fresh migration and populated upgrade paths,
and both local and pinned real S3-compatible adapters. It covers multipart resume,
identical/different replay, owner/Workspace/environment denials, live grant revoke,
concurrent quota/offset/revision disputes, cancellation after storage ACK, lost
commit ACK, checksum/MIME rejection, empty uploads, transactional event uniqueness,
expiry and abort during final storage I/O. A connection-pool assertion verifies
that storage I/O holds no database connection. The read-only storage CI workflow
starts PostgreSQL and the real S3-compatible fixture and repeats integration tests.
