# Coherent representation bundles (format 1)

A non-store processing request receives a monotonic Workspace request number.
Its exact original revision, SHA-256, frozen recipe, processing fingerprint and
profile revision identify its output. The processing fingerprint includes the
representation format version. There is no content cache across Workspaces or
revisions. Another request can reuse an already ready exact generation without
parsing or writing another copy. Concurrent first requests may build independent
generations; in-flight processing is not coalesced.

## Admission, verification and atomic publication

Migration 0113 adds durable output intents, representation generations, entries,
source blocks/segments and revision-scoped current heads. Each output is admitted
under the Workspace lock before storage I/O; declared bytes reserve the real byte
quota. A verified immutable write receipt moves reserved bytes to used bytes
exactly once. Receipt accounting can finish after authority changes because it
only acknowledges already admitted I/O. It never authorizes another write or a
publication. Failed, cancelled and abandoned outputs remain charged and invisible
until retention/GC reconciles and deletes them. No SQL transaction spans object
storage or conversion I/O. Upload part cleanup remains a separate lifecycle.

The worker persists the canonical structure and a private visual manifest as
checkpoints. It builds normalized Markdown, a heading outline (with physical page
metadata rather than invented headings), per-table JSON, actual PNG visual assets,
and SourceRefs. Internal chunked block text supports range reads without loading
a whole canonical document. Docling pictures now spool actual embedded images or
bounded PDFium page-region PNGs through the same durable publisher as OCR. A figure
without its visual, a missing output or inconsistent metadata prevents publication.
Native, OCR and model extraction methods and inferred flags remain distinct.
Figure preservation never claims semantic image transcription.

Every entry's streamed bytes, SHA-256, size and backend version are checked before
sealing. The canonical metadata fingerprint covers ordered entry/block/segment
records. Seal verifies object ownership/receipts, mandatory roles, figure assets,
counts, text bounds and contiguous character/byte segments. Source block batches
are inserted in parent-first topological order, while their canonical ordinals and
hash ordering stay stable; every independently committed batch satisfies its
parent foreign keys. Public manifest entries
contain IDs, logical paths, sizes and checksums; private object keys and backend
versions are excluded. The final manifest has its own immutable receipt/hash.

Sealing remains invisible. Only the job's final current-authority/fence check can
make a generation ready, update the revision-scoped head by request-number CAS,
write a ready event and acknowledge job success in the **same transaction**.
Workspace locks precede job locks. PostgreSQL guards require the current live job
fence and immutable source/recipe pins; sealed metadata cannot be changed. A
transaction failure rolls readiness, head, event and job acknowledgement back
together. A replacement attempt can publish the already sealed bundle without
parsing, rewriting or charging its objects again. Cancellation before final commit
keeps it invisible. An older completion can remain historical but cannot replace
a newer head. Updating the original creates a separate revision with no inherited
processing head.

## Read-only logical view and editable copies

The API uses only the Artifacts entrypoint and the artifacts Runtime interface;
it does not start a Run or acquire Agent/Network execution permits. All endpoints
require explicit project/environment and artifact_workspace_id scope.

| Path | Operation |
| --- | --- |
| `/v1/artifacts/{a}/revisions/{r}/representations` | GET the ready current generation for this exact revision |
| `.../representations/{g}` | GET an exact historical ready generation |
| `.../representations/{g}/entries` | GET signed, principal/query/generation-bound keyset pages; optional directory filter |
| `.../entries/{e}/content` | GET an authorized download with single Range/If-Range support |
| `.../entries/{e}/copy` | POST operation_id/path; create a separate editable Artifact |
| `/v1/artifact-sources/read` | POST a pinned SourceRef, offset and max_chars |

Entries expose read_only=true. Internal source text, visual manifests, storage
keys, backend versions, actor snapshots and worker fences are never listed or
returned. Downloads are private/no-store attachments with nosniff, safe UTF-8
filenames, SHA-256 ETag and the original source SHA header. A whole-object ETag
is not the digest of a partial range. Historical content still requires current
READ authority and a live logical source Artifact. Revocation/deletion blocks
subsequent resolutions; an authorized stream already in flight may finish.

Source reads require the exact generation, original revision/SHA and block. Any
supplied physical page/box, original line/byte coordinates and text encoding must
match the published source map. Text is read in independently hashed segments of
4096 Unicode codepoints; requests return at most 65536 characters. Offsets count
Unicode codepoints, not JavaScript UTF-16 units. Segment bytes, encoding, character
length and checksums are checked. Returned character coordinates explicitly use
canonical_block_text; original line/byte and page provenance remain separate.
Whole-block checksums can authenticate a paged block read; a different excerpt
checksum requires the exact bounded interval in one read. Original character
subranges are not guessed across CRLF/normalization. Raw-original-only and index
node resolution are expanded by their later reader/index steps.

Copy streams into the existing authorized resumable upload path, preserving
immutable generation/entry lineage under scoped foreign keys. Upload idempotency
includes that lineage; source visibility, size, SHA and MIME are verified before
admission and final publication. The copy gets a new Artifact/revision with
origin=copy. Neither the original nor the historical representation is edited.

## Qualification

Real PostgreSQL tests run on fresh and populated upgrades with local and actual
S3-compatible storage. They cover incomplete figures, missing objects, inconsistent
manifests, quota exhaustion, SQL rollback after a ready mutation, sealed recovery,
stale fences, cancellation, current interface revocation, Unicode paged SourceRef
reads, invalid source checksums/revisions/blocks/pages, read-only downloads,
editable-copy lineage/idempotency, exact ready reuse, out-of-order completions and
original revision changes. Converter tests additionally verify actual Docling
figure bytes and OCR assets. This qualifies the local S3-compatible implementation;
it does not claim an AWS-hosted acceptance run or a fully built product image.
