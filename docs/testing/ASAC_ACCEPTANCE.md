# ASaC history, locks and lifecycle acceptance

Scope: Woobe backend/Web and woobe-cli. Lipo integration is excluded by the owner. External service responses are not reproducible artifacts; restoring configuration never revives revoked credentials. This matrix identifies executable regression coverage, not a guarantee against every possible failure.

The live contract is `tests/integration/cli/test_control_plane_workflow.py`: PostgreSQL, API, workers, fake provider and the exact CLI pinned in `tests/unit/api/fixtures/woobe_cli_operations.json` and `.github/workflows/tests.yml`. The primary Agent/Network test invokes the isolated Draft, lease, deployment, signed receipt, managed policy, Web workbench and trusted Git helpers. Five complete CLI integration tests must pass; a zero-test or skipped run does not qualify this contract.

CLI paths below refer to [woobe-cli](https://github.com/A1b3rt0M3rcad0/woobe-cli). Backend paths are relative to this repository. Unit coverage is deliberately separated from live execution.

| Criteria | Regression evidence | Behavior checked |
|---|---|---|
| H01 | live isolated Draft helper; CLI `asac_hydration_test.go`, `asac_revision_fetch_test.go` | clean registry recovers immutable author closure; canonical root identity prevents duplicate native resources |
| H02–H05 | CLI `asac_history_test.go`, `internal/devworkspace/author_history_test.go` | remote selection changes differ from local edits, guarded checkout, fixed Release anchors and explicit rebase/merge |
| H06–H08 | live isolated Draft helper; `tests/unit/agent/test_asac_draft_store.py` | independent Draft lines, immutable lineage/parents, content deduplication without provenance collapse |
| H09–H12 | live isolated Draft/deployment helpers; `tests/unit/package/test_asac_definition.py`, Agent/Network candidate/publication tests; CLI revision/candidate tests | closed dependency digests, frozen Network constituents, exact tested Candidate, changed source rejected |
| H13–H14 | live managed lifecycle and Network publication; owner evaluation/publication tests | exact gate evidence required, publication leaves Production unchanged |
| H15–H16 | live deployment helper; `tests/unit/agent/test_asac_deployment_store.py` | stale plan and A→B→A changes rejected by monotonic generation |
| H17–H18 | live workflow lease helper; owner lease-store and CLI `asac_leases_test.go` | expiry/fencing and distinct workflow ownership even with the same credential |
| H19–H20 | live original operation/replay checks; CLI `asac_deployments_test.go`; owner deployment/outbox tests | lost response reconciles original operation, single effective activation; documentary/Git operations cannot activate Production |
| H21–H22 | live Web workbench helper; frontend ASaC workbench tests; CLI history/revision-fetch tests | Web checkpoint → exact evaluation → publication without fabricated Git commit; fetching history preserves working author files |
| H23 | live trusted Git helper and signed receipt helper | distinct scoped CI credential, clean committed clone without private `.state`, explicit trust and exact artifact verification |
| H24–H25 | live historical reads; owner history/Draft catalog tests; CLI retained hydration/history tests | scoped watermark/cursor completeness; unavailable object distinguished from available metadata |
| H26–H28 | live policy/binding/deployment checks; `test_asac_embedding_binding_guard.py`, `test_inspect_destination_bindings.py`, publication-binding tests | unavailable/revoked/stale dependency blocks activation; legacy endpoints enforce managed gates; portable and resolved runtime identities remain distinct |
| H29–H30 | live trusted Git helper; `tests/fixtures/asac_git_attestation.json`, signed-receipt fixtures and CLI canonical fixtures; six-platform native CI | exact committed bytes and later independent receipt, Python/Go canonical digests, explicit line-ending and physical path handling |
| H31 | live deployment helper; `test_runtime_identity.py`, `test_network_admission_identity.py`, terminal journal and recovery tests; CLI runtime-input tests | accepted Run identity, standalone Agent follows between Runs, Network Session pins its version, explicit YAML Session continuation |
| H32–H33 | live authorization boundaries; scoped history/capture tests and `test_asac_http_security.py` | partial scope never claims universal completeness; authority and concurrent source/generation capture rechecked |
| H34 | live Candidate/evaluation readiness; `test_asac_candidate_store.py`, Network candidate admission tests | incomplete Package preparation never advertised as a ready root; original operation remains inspectable |
| H35 | live copied-builder proof rejection; `test_asac_git_verifier.py`, `test_asac_git_store.py`, signed receipt tests; CLI Git/receipt forgery tests | untrusted claims, wrong scope, signature/digest tampering, revocation and expiry rejected; original accepted receipt immutable |

## Running qualification

The 2026-10-09 functional audit adds the following regressions. These checks do
not establish the cause of the report's four unavailable Network exports: their
stored graphs and bindings must be inspected through the scoped diagnostics.

| Audit item | Regression evidence | Resulting contract |
|---|---|---|
| F01 | CLI `asac_drafts_test.go`, `asac_leases_test.go` | absent/cleared checkpoints reconcile without writes; malformed or uncertain checkpoints cannot be overwritten |
| F02 | CLI `audit_parsing_test.go` | unknown nested commands fail with exit 2; bare groups and explicit help succeed |
| F03 | CLI `internal/output/audit_view_test.go` | compact receipts retain Candidate, preparation, evaluation and publication identities |
| F04 | `tests/unit/network/test_portable_export_diagnostics.py`, `tests/unit/package/test_export_conflict_diagnostics.py`; live Agent/Network export and managed round trips | complete exact graphs export; incompatible graphs fail with bounded code/path diagnostics, without substituting another snapshot |
| F05 | `tests/unit/agent/test_release_test_selection.py`; live deployment helper | Staging and Production tests use the exact selected immutable Release; changed selection is rejected |
| F06 | live `test_development_sync_postgres.py`; CLI clone tests | edited presentation names survive create/push and alias/path changes |
| F07 | CLI output regression tests | absent projected fields differ from explicit null; optional strict validation is confined to read-only inspection |
| F08 | CLI `package_author_test.go` | sealed sources remain verified and untouched; explicit `--structure-only` validation checks edited current author data without certifying the lock; transfers retain integrity gates |

Agent PATCH DTO tests additionally reject unknown fields instead of accepting
misspelled edits without effect. Help, output guides, Package authoring guides and
the canonical assistant skill accompany the CLI changes.

Use the canonical host unit/quality/selected architecture command from the contribution/testing guides, the tracked import-boundary checker, frontend test/build, and the Compose backend test contract. CLI requires `make check` (race), six archive verification and native/npm/skill smoke tests. Latest-SHA CI is required before merge; Linux-only smoke checks do not establish Windows/macOS compatibility.

Operator deployment must migrate forward through the ASaC migrations, explicitly configure Project managed policy and Production actors as appropriate, and provision instance receipt trust and optional trusted Git builders. Neither installing a new CLI nor a signed receipt grants these permissions. See [history](../runtime/ASAC_HISTORY.md), [Run identity](../runtime/ASAC_RUNTIME_IDENTITY.md), [signed receipts](../runtime/ASAC_SIGNED_RECEIPTS.md) and [Git provenance](../runtime/ASAC_GIT_PROVENANCE.md).


## 0.32.2 retest follow-up qualification

`tests/integration/cli/retest_operational.py` extends the primary live Agent/Network
workflow. It uses two CLI processes with independent configuration directories
and distinct workflow IDs against the same API/PostgreSQL instance: exactly one
concurrent lease acquisition succeeds, a mismatched workflow proof is rejected,
release/reacquisition increments fencing and an old proof cannot mutate selection.
These are independent clients on one test machine, not a multi-host network test.

A fault proxy forwards an actual deployment, waits for committed API acceptance
and truncates its response. The CLI reports unknown write outcome. Original
operation reconciliation by either client returns the same retained receipt;
replay does not duplicate selection. Concurrent rollback requests with distinct
plans for the same expected generation and valid workflow proof accept one
transition and reject the other by generation
CAS; response loss on the accepted rollback reconciles its original receipt.
SQL counts verify exactly one deployment per accepted operation and none for
the competing stale operation. Reader, Staging-only and Production-only
Control Keys are tested separately for read/plan/apply permissions without
Workspace administration. Managed Production rollback selects a previously
qualified exact Release, executes a real Runtime Key Run against it, then restores
the new Release; both transitions increment generation.

The provider in this reproducible CI topology is deterministic. This qualification
does not certify the operator's real Production deployment, four legacy Network
snapshots, real-provider latency/cost, physical multi-host failures, disk exhaustion
or load stability. The external retest's 182 recorded commands and seven smokes
are separate evidence and are not converted to independent test counts here.

## Unified deployment acceptance (2026-10-10)

The paired compiled CLI adds `tests/integration/cli/unified_deployment.py` to the
primary Agent/Network live contract. Coverage is cumulative with the owner tests
above; these rows do not represent ninety independent new tests or customer
Production certification.

| Unified criteria | Evidence | Checked boundary |
| --- | --- | --- |
| UDEP-001–024 | Existing deployment owner/store/live helper; CLI `deployment_unified_test.go` | Exact qualified selection, no-op generations, policy/binding CAS, original receipts and no legacy fallback |
| UDEP-025–032 | Unified live helper and CLI Staging drift tests | Exact selected UUID, clean native mode, no republish and Production-only grant |
| UDEP-033–048 | Unified live helper; existing immutable Candidate/Network and author custody regressions | Existing registered author → isolated Draft → Revision → passed Evaluation → Publication; same Release Staging/Production, negative smoke blocks Production |
| UDEP-049–064 | Unified dedicated-key cases; existing scoped HTTP/policy/security tests | Grant plus managed actor authority; no Draft/publication privilege; Runtime/control separation and revocation remains server-enforced |
| UDEP-065–080 | Unified truncated-response proxy, SQL row count; CLI step recovery/private-store tests; existing independent-process CAS/lease tests | No repeat after response loss or not_observed; scoped original intent, missing state blocks; independent processes share owner fences |
| UDEP-081–089 | Unified Runtime/rollback plus existing admission/managed rollback helper | Selected immutable Production identity, exact Network constituents and admitted Session continuity |
| UDEP-090 | Existing Runtime failure evidence; unified negative Staging smoke | A verification failure preserves actual prior commits; no implicit compensation |


Operation recovery is scoped by the consumed environment filter, then checked
against the persisted receipt and principal. Production-only delivery does not
need Draft authority. `test_asac_draft_store.py` and
`test_asac_http_security.py` exercise forged environment filters, other actors,
read-only Evaluation authority and access-check/actual-request agreement. The
capability `asac.operation_environment_reads` is required by the unified CLI.

Multi-host/load and customer-provider qualification remain operator acceptance;
the independent-client fixture uses separate processes/directories against one
disposable server. The official GitHub example is syntax/recovery-tested and uses
a separate protected deploy-only identity, pinned archive checksum and encrypted
checkpoint. Environment approval rules and credentials must be configured by the
operator; CI examples do not grant account access themselves.
