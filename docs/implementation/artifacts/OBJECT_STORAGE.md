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

This extraction does not claim the final Artifacts publication guarantees. Atomic
staging/promotion, crash reconciliation, immutable local retry and scratch lifecycle
are the following local-storage step. No public Artifacts upload is wired before
that hardening and its fault tests. A shared local disk still needs compatible
shared-volume deployment for multiple API/Worker instances; S3 qualification is
separate.

Step 07 contract checks cover empty/small/large streams, persisted metadata after
adapter recreation, range reads, immutable identity, checksum failure, bounded and
early consumption, idempotent deletion and exact old Knowledge keys/bytes including
replacement. Existing portable-document filesystem/S3 bounded-read regressions
remain enabled. Full mocked Knowledge, package/export and runtime regressions run
without changing legacy data or Release behavior.
