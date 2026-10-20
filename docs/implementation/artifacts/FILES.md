# File operations and logical directories

The public application facade exposes authorized text publication, bounded content
reads, directory listing, directory creation, move/rename, logical delete and
editable copy. HTTP exposure belongs to the following step. These operations do
not create a Session or Run. Trusted runtime callers may supply existing Run/Node
provenance; direct application writes leave those fields absent.

Text writes use the same resumable publication service and durable operation ID
as uploads. Replays preserve Artifact/revision identity; changed bytes, path or
provenance under the same operation conflict. UTF-8 inline reads/writes and editable
copies are explicitly bounded to 256 KiB. Larger content uses the streaming proxy
upload/download contract. An editable copy creates a new Artifact and copy-origin
revision, never mutates a representation generation. Historical reads pin the
exact source revision even if the current head changes during a copy.

Revision provenance retains origin (upload/application/agent/tool/processing/copy),
principal identity, operation ID and optional existing Run/Node IDs. Node provenance
requires a Run; direct writes never invent one. These immutable columns are
additive and protected by the existing SQL revision-update rejection trigger.

Files and directories share one live-path namespace. Server-created parent
directories have stable Artifact IDs and catalog history but no content revision.
A file cannot be an ancestor, collide with a directory or silently replace an
occupied path. Directory prefixes containing `%` or `_` are treated literally.
Directory pages filter immediate children in SQL and use signed, principal/scope/
directory-bound keyset cursors. A page sequence retains its catalog version and
historical paths; current logical deletion still redacts a file from old pages.

Move/rename preserves Artifact IDs and immutable content keys. It requires the
Artifact's expected version, records changed paths and advances one Workspace
catalog version atomically. Directory moves update the current tree in the same
transaction, refuse self-descendants/merges/collisions and are bounded to 1000
descendants. Larger tree moves return an explicit limit error before mutation.
Deletion requires CAS and rejects nonempty directories. Deleted revisions remain
retained for lifecycle cleanup and quota accounting; public reads stop immediately.

Mutation receipts fingerprint operation kind, target, expected version and path,
belong to the initiating principal and commit with catalog/history and an outbox
event. Retry returns the original mutation receipt, including after deletion;
changing the request under the same ID conflicts. Workspace locks serialize
publication, quota and path decisions. Write/rename/delete races cannot silently
overwrite another operation. Existing content revisions remain addressable by
Artifact/revision ID after a rename, while deletion blocks public historical reads.

Integration qualification uses both PostgreSQL migration paths and both local and
real S3-compatible storage. It exercises public composition, Unicode bytes/hash,
idempotent text/metadata operations, origin lineage, historical reads, editable
copy identity, literal prefixes, directory trees, collisions, nonempty deletion,
snapshot pagination and concurrent content/path mutations. HTTP end-to-end and
Runtime Key transport matrices are validated in the API step.
