# Package v1 acceptance

This matrix applies to create/import/export V1 in Woobe draft PR #179 and
woobe-cli draft PR #10. Explicit target update (CLI-PKG-10) is a later extension
under the supplied plan. No name-based upsert or alternate runtime is provided.

## Reproducible gates

The backend `tests.yml` checks out an exact CLI commit, embeds it in the binary
and runs the real API/worker/PostgreSQL/Redis/RabbitMQ/MongoDB Compose contract.
`tests/integration/package/test_cli_planning_postgres.py` validates the approved
plan before Apply, native persisted resources and receipts, cross-project
export/import/re-export, and a separate Runtime Key execution after deleting
all local source/export directories. Only provenance is excluded from descriptor
comparison; supporting files are compared byte for byte. Vector rebuild is a
new destination snapshot, not a claim of identical vector bytes.

The complete fixture combines primary/fallback models, generation parameters,
versioned Prompt, Contract, Behavior, External Context, stateful context policy,
Skills/resources/required Tools, protected HTTP authentication, fresh MCP discovery,
portable documents and embeddings. The Network adds multiple Agents, distinct
snapshot selectors, positions, limits and edges. Native child-run persistence
proves Tool execution when the Network's aggregate HTTP result omits Tool calls.

CLI `make check` retains all existing regressions, module verification, vet,
script tests and race tests. CI also runs bounded YAML/path/reference/lock/archive/
checkpoint fuzzing. Distribution jobs execute the complete shared fixture on
each real target OS/architecture rather than treating cross-compilation as proof.
Windows CLI credentials use per-user Credential Manager. Package operational
files retain native owner/DACL and locking checks in an existing private parent.

## T01–T26

CLI paths below are relative to woobe-cli; backend paths are under
`tests/unit/package`, `tests/unit/agent` or `tests/integration/package`.

| Case | Acceptance | Executable evidence |
| --- | --- | --- |
| CLI-PKG-T01 | Envelope and strict schema | `internal/packagefmt/contract_test.go`; backend `test_contract_parity.py` |
| CLI-PKG-T02 | Strict YAML/JSON and numbers | Contract fixtures and `FuzzDecodePackage` |
| CLI-PKG-T03 | Go/Python parity | Shared catalog/fixtures; `test_contract_parity.py`; native Python inventory smoke |
| CLI-PKG-T04 | Reference closure and graph | `contract_test.go`; `test_bundle.py`; `FuzzReferenceClosure` |
| CLI-PKG-T05 | Confined filesystem/archive | `packagebundle/*test.go`; `test_bundle.py`; native smoke |
| CLI-PKG-T06 | Bounded input and stable reads | Bundle limit, mutation, FIFO and hardlink tests; archive/path fuzzers |
| CLI-PKG-T07 | Exact inventory/digest | Golden inventory fixtures in both implementations and native smoke |
| CLI-PKG-T08 | Immutable lock | Bundle lock/tamper tests and `FuzzPackageLockDocument` |
| CLI-PKG-T09 | Flags/discovery | `cli/package*test.go`; registry/help tests |
| CLI-PKG-T10 | Offline/dry-run | Package validate/import/plan tests with HTTP and credential access counters |
| CLI-PKG-T11 | Destination authority | Checkpoint scope tests; live control-plane workflow; native permission/tenancy suite |
| CLI-PKG-T12 | Destination bindings | Planning/import binding tests; full protected-binding cross-project roundtrip |
| CLI-PKG-T13 | No protected values in artifacts | Public-plan masking, private receipt/checkpoint, safe diagnostics and live secret scanning |
| CLI-PKG-T14 | Unsupported server | Capability/schema checks and cancellation refusal tests; no Manifest fallback |
| CLI-PKG-T15 | Pinned plan | Prepared source/bindings/lifecycle mismatch tests; backend plan repository rechecks |
| CLI-PKG-T16 | Concurrent idempotency | PostgreSQL eight-way acceptance; public same-plan replay preserves operation/resource count |
| CLI-PKG-T17 | Recovery after acceptance | Lost-response CLI test, atomic native-effect/receipt test and lease recovery tests |
| CLI-PKG-T18 | Conflicting replay | Changed protected payload and retained idempotency tombstone tests |
| CLI-PKG-T19 | Polling/deadline/interruption | Polling tests, central deadline codes, one-POST recovery and ordered final JSONL |
| CLI-PKG-T20 | Cancellation | Operation worker cancellation/fencing tests retain committed inventory; native lifecycle tests |
| CLI-PKG-T21 | Atomic verified export | Transport/inventory proof; exclusive publication and partial-transfer tests |
| CLI-PKG-T22 | Versioned Network | Cross-project complete Network: multiple Agents, same Agent at distinct Draft/Release nodes, positions and topology |
| CLI-PKG-T23 | Native Knowledge | Public document/build/VectorSnapshot wait/resume, KnowledgeVersion and runtime after source deletion |
| CLI-PKG-T24 | Native lifecycle | Public Draft/Staging/Release/Production matrix; Network release does not activate standalone Agents |
| CLI-PKG-T25 | Existing client regression | Full `make check` with race detector; native Manifest/schema/pagination/protected-ref smoke |
| CLI-PKG-T26 | Native platforms | Six native CI targets: Linux/macOS/Windows amd64/arm64; complete shared fixture and checkpoint protection |

## Delivery slices

CLI-PKG-01 through CLI-PKG-09 are implemented by the shared contract, bounded
local loader, authorized transport/planning, native materialization, durable
operation/checkpoint, Knowledge build, Network lifecycle, frozen export and
these qualification gates. The operational API does not become a permanent
Package catalog. OAuth prerequisites remain destination-owned dependency waits;
unit tests prove they cannot reuse cached readiness or import source tokens.

## Tested revisions

Exact paired commit results are recorded in the two draft PR descriptions and
the backend CI artifact `cli-contract-*.json`, including client/server build
identity and public request outcomes. A schema version alone is insufficient
to establish compatibility with older releases. The published pair table in those PRs is the compatibility reference for tested
builds. Neither PR is merged or changed from draft by this delivery.
