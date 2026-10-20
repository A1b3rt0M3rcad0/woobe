# References, test validation and private recovery

## Exact Prompt and Contract selection

A native Draft save resolves `prompt_version_id` and `contract_version_id` for the
same Agent and Project. It freezes the selected Prompt text and Contract output
schema. Omit embedded `system_prompt` / `output_schema` when choosing references;
explicit content that disagrees with the selected version is rejected. Structured
Behavior and a versioned Prompt must describe the same instructions.

The saved Draft includes `runtime_config.contract_version_snapshot`. Editing a
native Contract later cannot reinterpret that saved capture or its export. Save
the Draft deliberately to adopt the new Contract, then capture/evaluate/publish
and deploy through the configured lifecycle. Existing incomplete immutable
captures are not repaired by choosing today's catalog or rewriting their hashes.

`project agent contract update AGENT_UUID CONTRACT_UUID` updates the existing
row. Include its last `updated_at` as `expected_updated_at` in the PATCH YAML to
protect a reviewed edit. A stale timestamp returns HTTP 409; read the current
Contract and review the differences before retrying. Blank native Contract names
have a stable default; nullable optional schemas/instructions are normalized.
Export also handles these legacy optional values and blank Prompt names.

## A passed test requires validation

`woobe agent UUID test --env draft --file testcase.yaml --yes` and
`woobe project agent release run-test UUID --file testcase.yaml --yes` execute a
saved snapshot. The second form includes `project_id`, `agent_id`, `release_id`
and `environment` in its YAML. `release test` only creates a record.

Expected output equality is optional. Effective output-schema validation is not
skipped because `expected_output` is absent. JSON Schema constraints and Woobe's
compact schema declarations are validated. Invalid JSON/output fails the test
with exit 6. `actual_output` exposes `provider_completed`, `output_valid` and
`contract_missing` for contract validation; `validation_errors` has stable codes.
A missing frozen schema for a referenced Contract records `CONTRACT_MISSING`
and does not invoke the provider. Plain-text Agents without a required output
contract continue to support ordinary execution/expected-output assertions.

JSON runtime remains strict, including historical `strict: false` records. The
authorized saved-test wrapper retains private output-validation evidence when
strict runtime rejects the Run; its test is failed, never passed. Other execution
failures remain distinct. No arbitrary provider error text is shown.

## Timeout is an unknown observation

Release-test execution uses a two-minute HTTP deadline unless `--timeout` was
explicitly supplied. Before sending one POST, the CLI records a UUID and request
hash under `release-test-intents/` beside its private configuration. It never
stores the testcase message, external context or credentials there.

A transport timeout/interruption does not establish remote failure or cancel the
remote test. The error preserves `test_id`, `write_outcome: unknown`, and the
exact read-only `recovery_command`. For example:

```powershell
woobe project agent release tests AGENT_UUID RELEASE_UUID --fields "id,status,validation_errors" --output compact
```

Find the recorded UUID. A pending record needs further observation; absence is
not proof that the POST was never accepted. Do not repeat POST to discover the
result. The CLI checks the advertised OpenAPI DTO for test_id before any execution; an
older backend is rejected without a POST. A compatible backend admits caller-selected `test_id` atomically: the
same identity/request returns the original pending/terminal record, while changed
inputs or scope are rejected. This does not execute another provider call.

## Shared dependencies and revision conflicts

`package doctor` checks compatibility and authority; it does not refresh a local
base. `PACKAGE_REVISION_CONFLICT` identifies the kind, native resource UUID,
expected/observed revision and binding path. Pull the owning Agent/Network,
review local versus remote changes and prepare a new plan. Preserve pending
checkpoints and reconcile uncertain writes first. Do not duplicate a Model or
silently advance the accepted generation to bypass a conflict.

## Issued-secret files

`--secret-file` creates an exclusive private JSON file after successful issuance.
The custody format is `format: woobe-issued-secret`, `file_schema_version: "1"`;
native response fields, including `data.key`, remain present for existing readers.
It is a versioned response envelope, not a plaintext token. Terminal output stays
redacted. Rejected requests leave no final file or empty stub. The writer pins the
parent directory, protects the temporary file (mode 0600 / private Windows DACL),
flushes it, and publishes without replacing an existing destination.

Both credential import and CLI-Key stdin login accept a raw token or a documented
issued-secret envelope; legacy native issuance envelopes remain readable. Empty,
failed, ambiguous, redacted, unsupported-version or malformed input is rejected.

```powershell
Get-Content -Raw -LiteralPath .\issued-control-key.json | woobe auth login --cli-key --stdin
Get-Content -Raw -LiteralPath .\issued-runtime-key.json | woobe auth credential import --stdin --name runtime
```

Keep these files outside author YAML, Git and `.woobe-lab`. Issuance requires the
appropriate explicit permission; a default Control Key is not automatically a
runtime-key administrator. If issuance committed but publication to disk failed,
inspect/revoke/rotate the issued resource rather than blindly issuing again.
