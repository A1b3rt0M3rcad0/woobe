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

Use the canonical host unit/quality/selected architecture command from the contribution/testing guides, the tracked import-boundary checker, frontend test/build, and the Compose backend test contract. CLI requires `make check` (race), six archive verification and native/npm/skill smoke tests. Latest-SHA CI is required before merge; Linux-only smoke checks do not establish Windows/macOS compatibility.

Operator deployment must migrate forward through the ASaC migrations, explicitly configure Project managed policy and Production actors as appropriate, and provision instance receipt trust and optional trusted Git builders. Neither installing a new CLI nor a signed receipt grants these permissions. See [history](../runtime/ASAC_HISTORY.md), [Run identity](../runtime/ASAC_RUNTIME_IDENTITY.md), [signed receipts](../runtime/ASAC_SIGNED_RECEIPTS.md) and [Git provenance](../runtime/ASAC_GIT_PROVENANCE.md).
