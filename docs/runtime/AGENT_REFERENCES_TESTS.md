# Agent references and saved-snapshot tests

Native Draft saves materialize Prompt/Contract version references owned by the
same Agent and Project. The selected Prompt content becomes `system_prompt`.
The selected output schema becomes `output_schema` and the JSON response schema.
Conflicting explicit embedded text/schema, or inconsistent structured Behavior,
is rejected. New captures freeze full Contract material under
`runtime_config.contract_version_snapshot`; their export does not reinterpret a
later Contract PATCH. Existing immutable captures/hashes are never rewritten.

Draft tests take a complete canonical execution snapshot before releasing the
short admission transaction. Runtime execution and test validation use that same
capture even if another editor saves Draft while the provider is running.
Tests validate output even without expected_output. Missing frozen output schema
for a referenced Contract records CONTRACT_MISSING without provider execution.
Invalid JSON/fields/schema constraints cannot produce passed. JSON runtime remains strict even for historical strict:false settings. The
authorized test wrapper receives private rejection evidence and persists a failed
output-validation result; ordinary runtime still rejects the invalid Run. Plain-text Agents without a
required output contract retain ordinary expected-output testing.

`POST /ai/agents/{agent_id}/release-tests/run` accepts an optional UUID `test_id`.
Admission locks that identity only in its short PostgreSQL transaction and commits
the pending record before the long provider call. The same identity/scope/request
returns its original pending or terminal result without another execution.
Different inputs return 409; other ownership is not disclosed. Use the existing
`GET /ai/agents/{agent_id}/releases/{release_id}/tests` to observe it. Request
fields remain message, external_context, environment and optional expected_output;
no credentials belong in a testcase. Interrupted response delivery does not
establish remote failure. A pending test is an observation, not proof of success.

Contract PATCH performs UPDATE with an atomic observed-updated_at comparison.
The caller can supply `expected_updated_at` from GET to protect its reviewed edit;
a stale value returns 409. The schema hash is computed from canonical input/output
schemas. Empty presentation names and nullable optional fields are normalized;
portable export also normalizes legacy Contract values and blank Prompt names.
Native package materialization normalizes before comparison so a retry reuses the
same author version instead of creating a duplicate or conflicting synthetic one.

For shared dependency conflicts, Package diagnostics expose kind/resource identity,
binding path and expected/observed revisions. Compatibility doctor does not adopt
a new base. Pull/review before a new plan; preserve and reconcile pending intents.
Never bypass generation checks or duplicate a Model to evade a stale local base.

The client custody/timeout procedure is documented in
[woobe-cli](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/CONTRACTS_TEST_RECOVERY.md).
Runtime-key creation still needs explicit authority. `host.docker.internal` needs
an appropriate trusted host configuration. A local conversation identifier is not
a remote Woobe Session UUID; use stateless execution or persist the remote ID.
External context must satisfy the selected snapshot's declared contract.

## Verification

`tests/unit/agent/test_report_contract_regressions.py` covers capture coherence,
missing/invalid output and replay. The native CLI integration report regression
covers PostgreSQL PATCH/CAS, actual provider execution, exact prompt text, later
Contract edits, portable YAML and failed CLI exits. Existing full lifecycle
integration covers Agent/Network Candidate evaluation, publication, deployment,
rollback, leases, managed authoring and restricted identities.

For Windows-origin Docker source trees, `.dockerignore` recursively excludes
node_modules and tsbuildinfo. Run `python scripts/verify_docker_host_exclusions.py`
to build/export a deliberately polluted four-package context with the actual
ignore rules, preserving source while refusing Windows dependencies/cache files.
