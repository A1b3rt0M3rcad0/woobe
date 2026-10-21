# Validation

## 0.34 report regression coverage

The local-deploy regressions check source scope, exact accepted ancestor digests,
parents-first missing history, read-only failure, and recovery after a local
checkpoint commit/intent-save interruption. Authentication and missing-scope
regressions are included in native CI, including Windows Credential Manager's
missing-reference exit code (3) and missing scope before any network call (2).

Run Windows tests in a disposable private directory outside an existing
`.woobe-config` tree. The temporary directory must have a private DACL; nested
registries and inherited public ACLs are environmental failures, not reasons to
relax private-state protection. Preserve a real project's `.state` and registry.
The CI matrix provides native OS/architecture evidence; a Linux run alone does
not qualify Windows Credential Manager or all six distribution targets.

## Unified deployment qualification — 2026-10-10

`make check` includes exact Release/Staging orchestration, read-only preflight,
capability refusal, scoped stable operation IDs, changed actor/input, forged
receipts, Staging drift, malformed suite refusal before authoring writes, exact
large-integer evaluation assertions, independent original plan/lease/apply/cleanup response
loss, and completed-intent observation. Recovery tests retain submitted state
when an original read is denied and recover after access returns without another
apply. Private checkpoint regressions cover locks, malformed/duplicate JSON,
symlinks and hard links; native CI verifies Linux/macOS/Windows on amd64 and arm64.

The official self-hosted CI example has shell syntax, stable intent, missing
checkpoint refusal and encryption/public-summary tests. Package qualification
verifies six archives, the native CLI, npm launcher and embedded/standalone
assistant payload; packaged smoke checks discover the new commands and reject
invalid deploy inputs offline.

[Woobe PR #205](https://github.com/A1b3rt0M3rcad0/woobe/pull/205) pins the compiled
CLI commit and runs the existing full five-test CLI/API contract plus both-kind
unified acceptance. The helper exercises accepted local closure, isolated Draft,
exact Candidate/Evaluation/Publication, Staging promotion, explicit rollback,
Production Runtime identity, truncated committed response with SQL uniqueness,
restricted deploy keys and failing Evaluation/Staging smoke gates. Backend owner
regressions verify persisted operation environments, actor scope, forged filters
and access-check/actual-request agreement. Latest commit results are recorded in
the paired PR checks; these descriptions identify executable coverage rather than
claiming ninety independent new tests or customer Production certification.

Protected Environment settings, actual provider behavior and physical multi-host
load remain operator qualification. Git signatures/provenance are independent
gates and are never inferred from a deployment workflow URL.

## Functional audit regressions — 2026-10-09

`make check` includes recovery of absent/cleared Draft checkpoints, refusal to
overwrite malformed/uncertain checkpoints, nested command error exits, compact
continuation IDs, absent versus null field projections, strict read-only
projections, clone presentation names, verified author copies and new sealing.
Fixtures for Network export errors verify bounded codes/paths without exposing
arbitrary backend messages. Package copy tests verify that tampered sources and
existing destinations are refused and captured source bytes remain intact.

Paired backend regressions exercise exact ASaC Staging/Production test selection,
Network capture failures and unknown Agent PATCH fields. Live CLI and managed
authoring tests run through the pinned binary, API, workers, PostgreSQL and a
deterministic provider, including edited names across clone/create/move/push.
The backend [acceptance matrix](https://github.com/A1b3rt0M3rcad0/woobe/blob/master/docs/testing/ASAC_ACCEPTANCE.md)
maps the audit items to their regressions. This coverage does not identify the
stored defects of the report's four unavailable Networks or certify every
production graph; the new scoped diagnostics identify the failing capture step.

## Assistant skill delivery — 2026-10-08

Current validation for the new skill is separate from historical backend evidence.
Installer tests cover exact multi-host payloads, update/removal, user/custom roots,
read-only modes, unmanaged/edited/extra files, malformed/traversal receipts,
links/hardlinks, size bounds, locks, ordinary rollback and concurrent-edit preservation.
All 59 Python tests passed, including both npm identities, candidate verification
and release recovery; all nine npm installer regression groups passed. Native Go tests additionally
cover embedding, offline command aliases, runtime separation, receipts, drift,
user/custom roots, locks, links, rollback and concurrent-edit preservation. The full local
Go race/module/vet checks and offline native/npm/skill smokes passed.

`make check` runs Node/Python regression tests plus formatting/modules/vet/Go race.
Distribution qualification builds six archives and both npm tarballs, verifies
source/version/content/checksums, then exercises the native binary and both npm
installers offline. All 38 fenced CLI skill examples are checked through packaged
help without server operations. CI repeats on all six native OS/architecture
runners and stores separate skill-smoke reports. PR checks carry the exact reviewed
revision evidence; this does not claim an assistant UI loaded the skill or certify
live remote operations beyond the separately recorded backend evidence.

Reproduce with [CI.md](CI.md). The regenerated command catalog currently lists
the executable entries in the generated [command catalog](OPERATIONS.md), including 193 HTTP operations; the optional skill installer
is a separate executable. Published CLI baseline and delivery evidence are available in GitHub Releases;
PR builds remain separate from published versions.

## Historical baseline — 2026-10-04

Go 1.27.1, Linux amd64. Module verification, formatting, diff checks, vet, race tests and native build passed. 89 test functions plus subtests. Statement coverage: 71.2% total, 69.9% CLI, 85.9% transport, 89.2% strict JSON, 82.9% manifest, 64.5% bounded schema validator.

Discovery exposes 234 executable handlers, including 188 HTTP operations. Six Linux/macOS/Windows amd64/arm64 packages built with verified SHA256, exact archive contents and embedded manifest schemas. Version-scoped `artifacts.json` is verified against archive bytes. The previous 37-commit CI passed all seven jobs (run 37243940695); final continuation CI is attached to the same PR.

The 30-commit continuation adds tests for duplicate/ambiguous input, secret-free manifests, canonical hashes, dependency IDs, large-number preservation, checkpoint parsing and key binding, malformed-success uncertainty, HEAD/read headers, network-free dry-runs, versioned schema discovery, authoritative body validation/local references/composition, partial projections and diagnostics. A composed client fixture creates Agent/prompt/contract/model/Network/draft, resumes without replay, rejects changed recovery credentials and distinguishes denied editor publication from explicitly selected publisher success.

At this historical baseline, real Woobe E2E was not run: no deployed test instance/credentials. Fixtures prove client behavior, not backend authority/tenancy or real DTO compatibility. Code coverage is measured evidence, not a numerical acceptance gate defined by the plan. Operation coverage, authorization matrices, real E2E and native credential protection/OS execution remain open. See `REMAINING.md`.

Resource continuation: all six kind/action mappings are checked against executable HTTP handlers. Tests cover v2 compile validation, large integers, typed IDs, unsupported actions, exact dependency references, compile-to-v1 execution identity, authorized diff, unchanged observation/ETag requirements, checkpoint resume and uncertain creation reconciliation without replay. Both schema files are verified inside all six packages. Final continuation CI is attached to PR #1.

Latest continuation tests selective capture/reapply with only requested fields, omission/null/revision preservation, unavailable or secret fields, mismatched identity/scope, new typed Skill/Project intents, same-route advertised pagination, cycle/scope/foreign-link rejection, partial redaction, dry-run preflight, build identity and composed-step progress reporting. COMPLETENESS.json covers all 101 original roadmap deliveries exactly; its report is regenerated and checked in CI.


## Portable Package qualification in draft PR #10

The implementation uses the exact Package schema catalog from Woobe draft PR
#179. Current local checks cover transport/inventory proof, bounded archives,
private checkpoints, lookup after lost Apply responses, public alias masking,
ordered JSONL completion, backend-compatible Unicode binding digests and race
detection. Windows Package protection uses native ACL/lock APIs. The complete shared fixture
and native tests passed all six OS/architecture jobs at `6cb726ced6514fa9f8b4f907682f476b65cd2762`
([run 37556624537](https://github.com/A1b3rt0M3rcad0/woobe-cli/actions/runs/37556624537)).
The workflow runs native Package tests on Linux/macOS/Windows for amd64/arm64,
plus parser/path fuzzing. Cross-compilation alone is not native qualification.

The current continuation passed `make check`, including full race tests, vet,
module verification and script regression tests. New bounded reference, lock,
archive and checkpoint fuzzers passed locally. The backend Package/native Agent/Network/authority/API regression suite passed
1640 tests; all 85 architecture self-tests passed. The exact supported client/server
build pairs and their public integration results are published in the
[Woobe draft PR](https://github.com/A1b3rt0M3rcad0/woobe/pull/179) and
[CLI draft PR](https://github.com/A1b3rt0M3rcad0/woobe-cli/pull/10).

These tests use separate administrative and Runtime Keys. The full Agent/Network
fixture compares all portable descriptors and supporting file bytes across two
Projects, then runs after removing local package directories. The provider/MCP
peer is deterministic; HTTP auth resolves destination Secret/Environment bindings,
Knowledge is rebuilt through the native pipeline, and native Network child runs
retain Tool execution evidence. No external production service is required.

## Contract/runtime report regressions — 2026-10-12

`make check` covers versioned private secret publication, rejection cleanup,
raw/legacy/versioned credential readers, native test uncertainty with one POST,
legacy-backend refusal, failed-test exit 6 and result retention. The paired backend
integration covers real PostgreSQL Contract PATCH/CAS, exact selected Prompt and
schema capture, strict invalid-output failure, preserved old capture export and
remote completion after client timeout. The full lifecycle suite remains required;
its checks qualify deterministic fixtures rather than customer Production.
The Docker gate builds a polluted nested-package context with the actual ignore
rules and requires host modules/compiler caches to be absent.
