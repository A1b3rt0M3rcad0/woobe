# Native structural document trees (engine structural/1)

The first-party structural indexer consumes a verified canonical generation. It
uses actual canonical headings and explicit parent relationships; repeated titles
remain distinct because node IDs derive from index identity and source block ID.
Missing heading levels do not create invented sections. Explicit canonical
parents, including forward references, are preserved. Without a heading hierarchy,
physical PDF pages or canonical blocks provide an explicitly labeled fallback.
Empty/scanned physical pages remain navigable without invented text. A source with
no readable blocks retains its partial/needs_ocr/unsupported coverage and cannot
become a falsely complete tree.

Every canonical block has one owning node, and container/section source ranges
cover exactly its descendants. Ranges are half-open canonical **block ordinal**
intervals within the pinned representation generation, not character offsets.
Discontinuous page/canonical membership remains discontinuous; taking a simple
minimum/maximum would incorrectly include unrelated source blocks. A node points
to its canonical block/checksum rather than storing another text copy. Bounded
titles are display metadata; citation/read authority always comes from SourceRefs.
Native/OCR/model extraction methods and inferred flags come from the immutable
canonical source metadata.

IDs are stable within one index. A semantically different frozen recipe creates
a new index without invalidating retained historical ones. An exact already-ready
generation/index can be reused without parsing or output writes. There is no
embedding or external model request. The woobe-structural-index/1 library pin is
an explicit first-party algorithm version, not an invented external distribution.

## Bounds and validation

| Resource | Bound |
| --- | --- |
| Canonical source blocks | 100000 |
| Tree nodes including root/page containers | 110001 |
| Depth | 64 |
| Source intervals per node | 1000, ordered/coalesced |
| Title | 512 Unicode codepoints |
| Child page | 1–200 nodes |
| Own-node text response | 1–65536 Unicode codepoints |
| Independently hashed source segment | 4096 Unicode codepoints |

Graph validation rejects cycles, missing/foreign parents, incorrect depths,
duplicate ownership/ordering, invalid source bounds, missing canonical blocks,
incorrect source checksums and incoherent subtree ranges. Native structural
sections require actual canonical heading blocks. Every physical page is present
in a page fallback. An empty complete tree is invalid. Indexing runs through the
existing owned blocking-I/O coordinator and finite job timeout, not an unbounded
recursive walk or another service.

## Durable publication

Migration 0114 adds versioned document_indexes and document_nodes. Scoped foreign
keys bind the job, original revision, canonical generation, source blocks and
parent/root node identities. Node batches insert parents before children and
commit independently. The node metadata fingerprint, counts, child relationships,
source checksums and exact subtree interval unions are verified before sealing.
The immutable manifest records source identity, engine/recipe, coverage and nodes;
it contains no parallel full-text document or storage key. Its bytes/hash are
stream-verified and charged through the same pre-I/O output intents as other
derivatives. Failed/cancelled output remains charged until lifecycle cleanup.

An extract_index pipeline seals the representation bundle, then the native index.
Both remain invisible. Final current-authority/fence validation makes the
representation and index ready, moves the revision head by request-number CAS,
writes their events and acknowledges job success in one transaction. Any later
error rolls all readiness/events back. PostgreSQL requires the current live job
fence, frozen engine and exact ready canonical generation. Sealed graph metadata
is immutable. Recovery uses durable checkpoints/sealed metadata and never repeats
an already completed index build or its storage charge.

## Read-only API

All routes require explicit project_id, environment and artifact_workspace_id,
current Artifacts READ authority and a live logical source Artifact. They use the
artifacts Runtime interface and acquire no Agent/Network execution permit.

| Path | GET result |
| --- | --- |
| `/v1/document-indexes/{document_index_id}` | Exact ready index metadata and root node ID |
| `.../nodes?parent_id=...` | Signed principal/query/index/parent-bound child page; omitted parent lists the root |
| `.../nodes/{node_id}` | Exact node, provenance, child count, source ranges and optional own SourceRef |
| `.../nodes/{node_id}/content` | Bounded own-node text with offset/max_chars |

Container nodes expose has_own_text=false and children rather than claiming a
whole chapter is their own text. A heading's own text is its heading; paginate
its descendants for their bodies. Later section-reader APIs can aggregate bounded
subtree views. Public SourceRefs pin index ID, node ID, representation generation,
original revision/SHA and block/page coordinates. A selected block must belong to
the exact node's source intervals. Forged sibling, foreign-index or stale-source
references fail rather than resolving a latest index. Historical indexes still
read their retained original revision after the logical file receives a new one.
Current revocation/deletion blocks subsequent resolution.

Bounded readers use ObjectStorage.head for declared immutable-write receipt
metadata, then authenticate only the selected source segments against their
independent SHA-256 values. HEAD is explicitly **not** whole-payload integrity
verification. Both built-in adapters provide it without reading object contents;
S3 uses HeadObject and local storage uses a safe file-size/receipt lookup. Strong
stat still streams/verifies the full payload for original verification and
publication. This preserves bounded physical reads for a very large leaf rather
than downloading it merely to check its metadata. Range downloads continue to
provide the expected whole-object ETag; it is not a checksum of partial bytes.

The optional local PageIndex Flash outline adapter, its exact upstream revision,
installation profile, limits and licensing are documented in [PAGEINDEX.md](PAGEINDEX.md).

## Qualification

Pure tests cover repeated/missing-level headings, non-Latin text, large leaves,
forward canonical parents, discontinuous page ranges, empty scanned pages, stable
IDs, cycles, range/checksum errors and depth/coverage limits. Real PostgreSQL tests
use both local and actual S3-compatible storage on fresh/populated migrations:
real Markdown/native-PDF/Docling conversion, signed child pages, bounded Unicode
leaf reads, exact SourceRefs, historical/new indexes, ready reuse, rollback after
ready mutations, manifest failure, sealed recovery, stale fences and live access
revocation. S3 HEAD is separately verified to issue no object GET while strong
stat still verifies bytes. The optional Docling converter remains absent from API
startup imports and is qualified separately from the lightweight base.

The text catalog and immutable cursor snapshots used to locate these trees are
documented in [SEARCH.md](SEARCH.md).
