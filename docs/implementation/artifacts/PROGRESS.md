# Artifacts execution ledger

Source: [the supplied implementation plan](PLAN.md), preserved verbatim; its
SHA-256 and 60 ordered steps are recorded in [manifest.json](manifest.json).
Architecture decision: [ADR 0006](../../adr/0006-artifact-workspaces-document-runtime.md).
Baseline and ownership: [BASELINE.md](BASELINE.md).

Branch: `feat/artifact-workspaces-document-runtime`.
Base: `3dbcb3e1a7559f4a50ebca320e411933d46e8012`.

## Current state

Step 01 is complete. Baseline, ADR, ledger and CI guards are committed. The single
[PR #220](https://github.com/A1b3rt0M3rcad0/woobe/pull/220) is OPEN, Draft and has no
auto-merge. GitHub API connectivity recovered after the environment network draft
update; existing platform authentication worked without adding credentials.
PR #219 remains unrelated and untouched.

Step 02 is complete: exact pinned client snapshots, source/hash/license manifest,
local Go workspace and read-only client CI are included. Original client repositories
remain unchanged. CLI make check/build, both Go SDK modes, Python SDK 34 tests,
Ruff/build/Twine, source hashes and the new workflow validation passed. Step 03 is complete: domain identities/lifecycles, versioned DTOs, capability ports,
canonical schemas/fixtures and the Artifacts architecture policy are validated.
31 combined domain/contract/guard tests, Ruff and all nine architecture policies pass.
Persistence, authorization and adapters are not advertised as implemented. Step 04 is complete: additive PostgreSQL migration 0107, scoped catalog/revision
repositories and transactional Unit of Work passed 14 real PostgreSQL tests across
fresh and populated-upgrade paths. The native mocked regression passed 3135 tests
and 10 subtests. See PERSISTENCE.md.

Step 05 is complete: shared current-principal authority, explicit Artifacts Runtime
interface/actions, scoped live grants and restrictive Release/node intersection are
validated. 399 authority/Core/Artifacts regressions and 14 real PostgreSQL cases
passed. See AUTHORIZATION.md. Step 06 is complete: independent idempotent Workspace provisioning/resolution,
CAS metadata/lifecycle operations, scoped grants, signed SQL-filtered pagination
and public short-transaction composers are validated. 36 real PostgreSQL cases,
55 domain/guard tests and 3159 mocked regressions (plus 10 subtests) passed.
See WORKSPACES.md. Step 07 is complete: shared streaming object storage contract, local implementation
and Knowledge compatibility facade are validated with 9 targeted tests and 3165
mocked regressions (plus 10 subtests), with architecture checks passing.
See OBJECT_STORAGE.md. Step 08 is complete: atomic closed-handle promotion, immutable retry/metadata
reconciliation, cancellation-safe OS resources, staging cleanup and private scratch
passed 29 targeted/fault tests, including a deterministic reader/promotion race. A 64 MiB stream used under 8 MiB traced Python heap.
Full mocked regressions passed 3185 tests plus 10 subtests after the publication-lock
correction; 100 additional concurrent immutable-write pairs each had one winner
and one explicit conflict. Step 09 is complete: shared S3 streaming/conditional multipart, verified SHA-256,
ACK reconciliation, safe abort and Knowledge facade passed 40 targeted tests
(including 11 against a real pinned S3-compatible service), architecture, Ruff and
actionlint. The full mocked regression passed 3185 tests plus 10 subtests.
No real AWS qualification is claimed. Step 10 is complete: owner-scoped resumable proxy parts, quota reservations,
short database phases, immutable verified finalization, durable receipt/outbox and
concurrent abort/expiry/CAS reconciliation passed 89 integration/registry tests.
The existing security integration suite plus Artifacts authority passed 40 tests;
full mocked regression passed 3187 tests plus 10 subtests. See UPLOADS.md.
Step 11 is complete: idempotent bounded text publication, immutable provenance,
logical directories, atomic CAS rename/tree move/delete, historical directory
pages and editable copy identity passed 123 real integration cases. Full mocked
regression passed 3187 tests plus 10 subtests; 83 domain/storage/guard tests and
all architecture policies passed. See FILES.md. Step 12 is complete: direct Workspace/file/upload/download APIs, exact reviewed
Control permissions, Artifacts Runtime interface, scoped errors/response schemas,
proxy Range/CORS and live logout/grant/key revocation passed 147 integration tests.
Full mocked regression passed 3187 tests plus 10 subtests; native API/Workers are
reloaded and healthy. See HTTP_API.md. Step 13 is complete: immutable scoped recipes, passive component/library/model
readiness contracts, exact Workspace defaults/CAS and reproducible reuse identity
passed 155 integration cases, then 12 final profile/constraint cases; full mocked
regression passed 3198 tests plus 10 subtests. Store-only remains available and no
unimplemented parser/indexer is advertised. See PROCESSING_PROFILES.md.
Step 14 is complete: existing Worker process integration, standard durable outbox/
inbox delivery, fenced attempts/checkpoints/heartbeats, current authority checks,
reconciled cancellation/uncertainty, bounded admission/concurrency and fair
Project/Workspace selection passed 211 integration cases plus 12 final pipeline/
retry/factory cases. Actual process-death recovery passed on both adapters.
Full mocked regression passed 3198 tests plus 10 subtests. Store-only verification
is qualified; format adapters are delivered next. See PROCESSING_JOBS.md.
Step 15 is complete: deterministic native TXT/Markdown/JSON/CSV extraction, strict
encoding, original byte/Unicode/line provenance, structured untrusted data and
streamed private canonical checkpoints passed 117 unit/guard cases, 227 real
integration cases and 4 final ranged-read/ACK-recovery cases. Full mocked regression
passed 3219 tests plus 10 subtests before two additional passing unit cases. All
nine architecture policies passed. See NATIVE_TEXT.md. Step 16 is complete: resource-bounded isolated PDF extraction/rendering, physical
pages/printed labels, precise protected/invalid errors and explicit partial/OCR
coverage passed 139 targeted cases and 235 integration cases. The final renderer
dependencies also passed 8 repeated real PostgreSQL/storage PDF cases and 3229
mocked regressions plus 10 subtests. See NATIVE_PDF.md. Step 17 optional Docling
integration is next. Hugging Face model acquisition is currently refused by the
network proxy; a narrowly scoped network draft is saved and awaits environment
configuration activation. No weight-based profile is represented as qualified.

The stage commit carries `Plan-Step: 01/60`; a file never records its own containing
commit SHA. CI reconciles commit subjects/trailers against the execution manifest.
No final acceptance is claimed. Runtime capabilities are exposed only when their
authorization, service and adapter steps are implemented and validated.

## Validation and resumption

Local step 01 validation passed: 14 guard tests, Ruff for both new Python files,
117 combined quality-gate/architecture tests, and all eight governed module
architecture checks with zero violations. Commands and observed results are
recorded in the manifest; the initial API connectivity failure was resolved and PR creation/status verified.

Use the baseline commands and outcomes in BASELINE.md. Run the new guard tests
with `.venv/bin/python -m pytest -q tests/architecture/test_artifacts_plan_guard.py`.
Validate the ordered committed series with
`python3 scripts/validate_artifacts_plan.py --base 3dbcb3e1a7559f4a50ebca320e411933d46e8012`.
CI supplies its real PR event file and refuses non-Draft execution. Final audit
additionally supplies `--final` and requires exactly 60 completed, evidenced steps.

Never create empty commits or mark steps complete with placeholders. Correct a
step before committing it; later corrections require a controlled reconciliation
of its responsible commit. No merges, automatic mirrors, tags, production changes,
release/publication or Ready-for-review transition are part of this delivery.
