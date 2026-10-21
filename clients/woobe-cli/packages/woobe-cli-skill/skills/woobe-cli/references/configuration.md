# Remote Project configuration

Use this flow when developing resources without access to Provider/Tool secrets.
It requires a backend advertising `project_configuration.v1`.

1. Declare a reference with `woobe project configuration declare PRIMARY_API_KEY
   --kind secret --format token` (one complete command line).
2. Bind resources using typed remote references. Read
   [dependencies](dependencies.md) for the resource workflow. Provider requests
   use `authentication.type: api_key` and
   `authentication.fields.api_key: {source: project_environment, key: PRIMARY_API_KEY}`.
3. An authorized operator fills values and approves the intended destination in
   Project → Environments. Never request a token in chat, print it, or save it
   in author YAML, instructions, command flags or tool transcripts.
4. Inspect `woobe project configuration list --env draft`. Use `--status missing`
   and `--search PRIMARY` to narrow results. Then run
   `woobe project configuration check agent AGENT_UUID --env draft` or
   `woobe project configuration check network NETWORK_UUID --env staging`.
   Replace the UUID placeholders with real target IDs. `blocked` exits 6;
   `unknown` or incompatible capabilities exit 9. Resolve these diagnostics
   before execution. Metadata readiness does not certify an external test.
5. Run only the test/execution authorized by the user after the server accepts
   its configuration. Filling values never automatically reruns or deploys.

`woobe project configuration usage KEY_UUID` reports retained consumers. Replace
`KEY_UUID` with the declaration ID. List and usage support bounded pages with
`--offset`; list also accepts `--limit` up to 200. The default Environment is
Draft. No configuration command needs `.woobe-config` or a local secret store.

If capability negotiation fails, report the incompatibility. Do not fall back
to reading local protected files or using a value from another Environment.
`--dry-run` is offline metadata preview, not evidence of server readiness.

Bind an existing connection with `woobe project configuration bind provider CREDENTIAL_UUID --key PRIMARY_API_KEY`. Tool bindings support explicit api_key, bearer, basic, headers or none; use declared names only. The server compares the binding revision and rejects concurrent edits. Migrate existing inline credentials before replacing their authority.

For an HTTP group, bind one stable route ID:

```sh
woobe project configuration bind tool TOOL_UUID --route orders --type bearer --field token=ORDERS_TOKEN
```

The backend must advertise route bindings. An omitted route definition inherits
connection authentication; explicit route `none` suppresses its private headers.
Approve the route's fixed destination, never broaden it to make a failure pass.
Package 2.0 route YAML retains these references and requires matching declarations.
Valid reference metadata remains readable in terminal output; a redaction marker
is not a replacement reference. Metadata round-trips preserve bindings; changing
or removing one requires configuration-bind permission.

Use `woobe project configuration test provider CREDENTIAL_UUID --env staging` only when an external connection test is requested. For MCP discovery use `woobe project configuration test tool MCP_TOOL_UUID --env draft`. These make outbound requests and may save MCP discovery; they do not execute an Agent or arbitrary HTTP Tool. `check` remains read-only with no external I/O. Never retrieve a value or substitute a local token to make readiness succeed.

For packages, use negotiated schema `2.0` and explicit `--structural` installation as described in [packages](packages.md). Never provide or recover local secret values for this flow. An installed structure can still require configuration and preparation.


Knowledge installed structurally retains a `PENDING_PREPARATION` vector snapshot.
After the operator fills the referenced values and approves their use, read its
`build_config_hash` with `woobe project knowledge snapshot get SNAPSHOT_UUID`.
Create a YAML file containing `project_id`, `environment` and
`expected_build_config_hash`, then queue it explicitly:

```sh
woobe project knowledge snapshot prepare SNAPSHOT_UUID --file prepare.yaml
woobe project knowledge snapshot get SNAPSHOT_UUID
```

The queue request checks the exact build intent and configuration before accepting
work. Repeating the same accepted request does not create another build. `BUILDING`
is pending; wait for `READY` before Candidate/release preparation. A failed or
changed intent requires a new snapshot version. The CLI does not supply values.

Legacy migration is administrative work, separate from development. Check the
server's `migration_source_kinds` before selecting Provider, Secret or Tool sources.
Recognized Secret header templates can migrate without changing author snapshots;
The Tool adapter handles global and route-local literals without retained snapshots. OAuth,
retained inline snapshots and mixed authentication require
explicit review; never broaden a route or rewrite history to bypass it.
Do not infer whole-Project completion from one successful source-family batch.
Old Provider/Tool material writes affect a shared compatibility slot and require
value-write authority for all three Environments. A limited operator must use the
central operation for the selected Environment. An ignored field in an old request
does not narrow its scope; never suggest it as a permission workaround.
`CONFIG_MIGRATION_WORK_PENDING` requires resolving active/uncertain Runs, builds,
operations or unconsumed plans; never invent a fleet/drain attestation. Read the
server migration runbook before advancing a reviewed job. Generic `woobe request`
can inspect its reports; migration never requires local secret files.

A copied legacy name does not grant a new Tool access. Use explicit destination
approvals. After Environment separation, `LEGACY_ENVIRONMENT_REQUIRED` means an
old writer is ambiguous; select the intended Environment in central configuration.
New compatibility Secrets retain their UUID but store material centrally. Adding
one to a new Tool requires Secret read and use-policy write authority for all
three compatibility Environments; failed approval rolls back the Tool write.
Do not retry with broader credentials just to bypass a denial. Existing revoked
policies remain revoked after metadata edits. MCP creation with a Secret template
defers discovery until explicit authorized connection preparation.
Newly supplied sensitive global HTTP/MCP header literals are stored centrally;
Tool responses contain owner references, not the submitted material. Prefer
reference-only definitions and central value editing. Do not copy private legacy
aliases into YAML; use the configuration binding operation. Literal replacement
does not grant a different destination or restore revoked authority.
Existing Tool execute and MCP refresh use Draft with those legacy contracts.
Old captured Tool-write authority can preserve Draft MCP refresh, subject to the
current grant and destination policy. New keys need explicit validation authority.
The translation does not authorize central test endpoints or other Environments;
never manufacture legacy provenance or retry a denial with a broader key.
Revoked destination authority is exit 4; blocked metadata readiness is exit 6.
Use explicit configuration preparation for Staging/Production instead of assuming
an old refresh command selected the runtime Environment.

Managed edits may explicitly reuse the same existing Provider UUID with a central
legacy route. Keep that captured identity and review `binding_source` in the
plan. Do not turn it into a new key reference expecting a legacy fallback, or
replace it with a local secret. A deployment checks both binding revision and
current activation evidence; replan after value rotation.

HTTP Tool URL templates need a fixed origin. Path parameters require approval of
the static parent path, and rendered destinations are checked at every send.
Do not broaden an approval to make a changed endpoint pass.

Start a Project-wide review with `woobe project configuration summary --env draft`.
It reports metadata for current selections, not historical costs or execution
success. The default bound is 50 Agents and 50 Networks; set `--limit 1..200` and
follow `next_cursor` with `--cursor CURSOR` in the same Project and Environment.
Page counts are not global totals. `has_next` is enumeration; `page_complete`
and `page_state` describe this page. Even the last ready page exits 9 because it
cannot qualify earlier pages. Pages observe different times, so do not add shared
key counts or infer permission from their aggregate. Incomplete exits 9, a complete
blocked Project exits 6. Follow with an exact target
`check`; never treat incomplete aggregate counts as permission to execute.
