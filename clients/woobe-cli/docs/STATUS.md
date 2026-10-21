# Current implementation status

Updated 2026-10-10. ASaC history, workflow leases, isolated Drafts, exact
Candidate evaluation/publication, fenced deployment and trusted Git proof
commands are implemented. Unified Agent/Network delivery is tracked in
[CLI PR #63](https://github.com/A1b3rt0M3rcad0/woobe-cli/pull/63) and
[Woobe PR #205](https://github.com/A1b3rt0M3rcad0/woobe/pull/205).
It adds exact Release deployment, captured Staging promotion, evaluated local
ASaC delivery, optional separate Runtime smoke and private original-operation
recovery. See [DEPLOYMENT.md](DEPLOYMENT.md) and [CI_DEPLOYMENT.md](CI_DEPLOYMENT.md).
The protected deploy-only example runs on a self-hosted runner and restores an
encrypted checkpoint across attempts; it does not configure an operator's secrets
or protected Environments. Backend capability `asac.operation_environment_reads`
is required so Production recovery does not demand a Draft grant.

Release availability follows merged source and the release manifest. Confirm
`woobe agent AGENT_UUID deploy --help` before using new instructions on an installed
package. PR checks retain exact reviewed source/native qualification; draft
artifacts are not an npm release.

Use [GitHub Releases](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases) and the
permanent release manifest for the current published version and exact source
commit; a PR build is not a published package. The automatic release workflow
validates the merged source before publishing native assets, the image and npm.

The historical server delivery is tracked in
[Woobe #199](https://github.com/A1b3rt0M3rcad0/woobe/pull/199), including the
H01–H35 acceptance matrix. Installing a client does not deploy or migrate the
backend, enable managed Project policy or configure instance/builder trust.
Use capability discovery and the current lifecycle/signature guides for the
required server protocol and operator configuration. Lipo is outside this scope.

The native CLI embeds the portable assistant skill and installs it offline with
`woobe skill install`, without Node/npm, login or development config. The optional
standalone npm skill package is prepared but is not claimed publicly published.
Its payload and compatible installer tarball ship with validated release assets.
The bundled skill compatibility floor is 0.32 for the provenance guide.

Current guides are listed in [INDEX.md](INDEX.md). Historical roadmap records below
retain their dated limits; they do not grant merge authority or certify production.

## Historical implementation checkpoints

The dated records below retain their original evidence and limitations. Branch,
PR, release and incomplete-work statements in them describe those checkpoints;
use the current guides and current discovery for today's behavior.

Updated 2026-10-05 (America/Sao_Paulo). The canonical Go client is in `A1b3rt0M3rcad0/woobe-cli`; implementation PRs #1–#7 are merged at `a9c6ace053ea1f3e57abbb5d372f77010211ad56`. This continuation is on `feat/cli-pagination-contracts`; the code revision `659baea23458380b84bc7059d2a544c9c06fc1f5` passed all six [CLI CI jobs](https://github.com/A1b3rt0M3rcad0/woobe-cli/actions/runs/37385398090). No new PR, merge, tag or release is claimed.

## Backend acceptance

[Woobe PR #177](https://github.com/A1b3rt0M3rcad0/woobe/pull/177) at `77c53832f0e5b35488d1574b3cf62777486f5189` was **merged on 2026-10-06**. Seven backend workflows passed on that SHA. Required tests compile the pinned Go client and run API, workers, PostgreSQL, Redis, RabbitMQ and MongoDB with a deterministic model provider.

Verified scenarios include Project/provider/Agent/Network configuration, staging and production publication, Agent and Network rollback, runtime execution with separate keys, category lifecycle, revision-fixed grants, stale ETags, constrained authority, administrative replay, key rotation and old-key refusal. This evidence replaces the older claim that backend acceptance was entirely unavailable. It does not imply approval, merged availability or complete acceptance of every roadmap phase.

The pagination/backend continuation is `8ab9d13953c1cd77462af85a3a3a957395141edc`. Its required live CLI tests passed, including all four body-paginated routes and a session reader restricted to the Agent and staging. Catalog revision `2026-10-05.2` includes the session GET under `run:read`; the authority guard evaluates the actual environment query and the default draft filter. Exact results of the remaining workflow groups are maintained in PR #177.

## Delivered client behavior

- Go 1.22 language minimum, Go 1.27.1 toolchain and pinned runtime SDK; 241 executable handlers including 190 HTTP operations.
- Explicit Workspace/Project contexts and separate administrative/runtime credential selection; cookie/CSRF sessions, private POSIX credentials and per-user Windows Credential Manager. Direct CLI Key login discovers its Workspace/Projects per connection; Windows human-session persistence remains open.
- Registry-derived help, flags and invocation schemas; server OpenAPI discovery and bounded request-body validation, read-only manifest preflight and opt-in validation before writes.
- Workspace/Project administration; Agent/Network configuration and release lifecycle; Tools HTTP/MCP, Knowledge, providers/models, Skills, ChatSurfaces, key lifecycle, runtime and diagnostics.
- No automatic mutation retry; strong preconditions and idempotency headers are forwarded where supported. Secret issuance requires an exclusive private destination; ordinary outputs are redacted.
- Versioned manifests, typed dependencies, selective capture, exact numeric state comparisons, locked checkpoints, partial reports and explicit-ID reconciliation. A GET observation does not attribute the original uncertain write.
- Reviewed `--all` pagination for category list/history, authority audit and Agent sessions. Three body protocols preserve all filters; bounds cover pages, aggregate bytes and total traversal deadline. Single-page and partial output report collection completeness explicitly. See [PAGINATION.md](PAGINATION.md).
- Six packaged OS/architecture targets; CI executes native packages on Linux/macOS/Windows. Native smoke now exercises body pagination and partial-collection metadata against loopback fixtures; live backend acceptance is separate.

## Remaining work

Native credential providers and sessions, full declarative observe/plan/apply reconciliation, complete input schema/dialect/route/query coverage, stream reconnect/replay/gaps, complete semantic export/import remain. Pagination is implemented for all four reviewed body-paginated administrative routes, but full semantic export remains partial and unknown endpoint protocols are not inferred.

The [101-item audit](COMPLETENESS.md) now includes the separately delivered backend evidence. Its percentage measures delivered roadmap items, not effort or production readiness. No full phase acceptance is asserted merely from individual tests.

## Request validation continuation — 2026-10-05

Shared request-body validation now enforces readOnly/writeOnly request direction, validates UUID/date/date-time formats and refuses unsupported advertised OpenAPI/JSON Schema dialects. Regressions exercise validate-input, opt-in HTTP writes, manifest preflight/apply and checkpoint evidence. Native package smoke also checks valid/invalid UUID and timestamps, read-only refusal and write counts. Path/query and full DTO/dialect/composition coverage remain partial; no roadmap item is promoted solely for this narrower delivery.

## Path/query and DTO continuation — 2026-10-05

Opt-in parameter validation now covers canonical HTTP reads/writes, standalone
read-only validate-input and manifest preflight/apply. It enforces advertised
required fields, primitive formats/types, nullable/composed types, scalar
multiplicity and form arrays; preserves context/route aliases; refuses unknown
parameters and unsupported styles. Inline DTO `$defs` are inspected with valid
document-relative references. Native package smoke checks preflight and validated
pagination, and adversarial parameter fuzzing ran 33,051 cases locally.

The backend continuation adds advertised DTO body contracts to Agent,
provider/model, prompt/contract, model configuration/release-test, Knowledge,
Tools, session/message/job and identity operations, plus consumed Agent-session
query filters. The live acceptance workflow now requires this client validation.
Historical backend validation is recorded in merged PR #177; local unit/schema checks
are not a substitute for the required live gate. Full input validation remains
partial: arbitrary dialects/compositions, object/content parameter serialization,
header/cookie coverage and DTO/controller custom validation remain unqualified.
The full-plan delivery count remains 62/101 (61.4%).


## Workspace category continuation — 2026-10-05

AuthorityCategory definitions now compile/import without requiring a Project,
while mixed documents require every kind's owning scope. Configuration-only
imports do not assign authority; edits require explicit ID/ETag. Selective capture
and immutable revision diff are implemented. Permission/condition order is ignored
for category comparison; identity, Workspace and strong ETag bind skip-unchanged.
Checkpoints suppress completed creates, but do not infer lost writes by name.

`make check` passed with race tests. Native fixtures now cover Workspace category
compilation and revision comparison. Backend PR #177 adds required live
import/preflight/resume/unchanged/capture/pinned-grant scenarios and validation of
publication and MCP permission inputs; their current head results are maintained
in that PR. The prior backend head `acb71e17` passed all seven workflows and prior
CLI `6fdb4663` passed all six jobs. These are prior-revision evidence, not approval
of this new continuation.

The ledger is now **63/101 (62.4%)**, 36 partial and 2 pending. Category definition
import closes 8.7; category-applied grant migration stays partial in 4.7. Full
reconciliation, native protected credentials/sessions, exhaustive schema and
principal qualification, streams, semantic export and release gates remain.


## Protected references and MCP permission continuation — 2026-10-05

Thirty additional commits span CLI and the existing backend draft PR. Protected
manifest references now support Tool/provider configuration through the POSIX
private-file store, with deferred preflight, in-memory wire values, hash-bound
checkpoints, echo redaction and explicit refusal of uncertain secret reconciliation
or skip-unchanged. Windows credential protection is delivered; native Linux/macOS desktop keychains remain optional.

MCP permission inputs are canonical in every direct write and resolved manifest
write. The backend refuses ambiguous/undiscovered remote names before changing
anything and validates MCP provider discovery. Reviewed read contracts cover
Agents, providers, Knowledge, Tools, message paging and Skills; Skills import and
six MCP OAuth operation bodies use their existing DTOs. Backend local validation
passed 1340 tests; CLI make check passed. Expanded live gates and current CI SHA
evidence belong in PR #177; previous pair 747ee0dd/c7209fc7 passed all seven
backend workflow groups and all six CLI jobs.

The ledger is **66/101 (65.3%)**, 34 partial and 1 pending. Items 6.3 and 8.8
are newly delivered. Item 9.3 is an audit correction: its CI/integrated-suite
criterion is met; full phase acceptance is a distinct criterion and remains
unverified. Grant/assignment migration, exhaustive reconciliation, native
credentials/sessions, full DTO/dialect coverage, stream recovery, semantic
export and tagged installation/release remain open.


## Portable Package delivery

Historical package delivery: CLI PR #10 paired with Woobe PR #179 (now merged). Package is independent of Manifest and includes native Agent/Network snapshots, protected destination bindings, durable checkpoint reconciliation, fresh MCP discovery, portable Knowledge rebuilding and verified atomic export. The complete shared composition fixture is tested natively on all six distribution targets. Exact paired integration evidence and the T01–T26 qualification gates are recorded in [VALIDATION.md](VALIDATION.md).
