# CLI workflows

Project configuration can be declared without access to its values. Use
`woobe project configuration declare PRIMARY_API_KEY`, associate it with
`woobe project configuration bind provider CREDENTIAL_UUID --key PRIMARY_API_KEY`,
and have an authorized operator configure it in **Project → Environments**.
`woobe project configuration summary --env draft` gives a bounded overview;
`woobe project configuration check agent AGENT_UUID --env draft` checks the
selected target without running it. See [Configuration](CONFIGURATION.md) for
permissions, compatibility and failure states.

For a development clone missing private native bindings, run
`woobe agent '@support' bindings recover --dry-run`, then recover and explicitly
bind Providers. Networks use the same command. See [ASaC](ASAC.md) for exact
snapshot checks and the distinction between recovered identity and author base.

## Coding assistants

Prepare the whole project with `woobe init --agents codex`, `--agents codex-legacy`
or `--agents claude`; see [project setup](PROJECT_SETUP.md). For skill-only setup,
install offline with `woobe skill install --agent codex` or `--agent claude`.
Use `woobe skill status`, `uninstall` and `agents`; `--project-dir` selects a local
folder and `--scope user` installs for the current user. No key, context, Node.js,
npm or `.woobe-config` is required. Runtime `woobe skill list/create/...` is separate.

The embedded [assistant skill](AGENT_SKILL.md) routes to task-specific offline
references and YAML examples. It teaches pull/edit/validate/diff/push to Draft,
shared dependencies and explicit lifecycle operations using these same commands.
The optional npm installer shares the same receipts and payload; no remote writes
or authentication happen on skill install.

## Build and discovery

```sh
go build -o bin/woobe ./cmd/woobe
bin/woobe help --output json
bin/woobe schema --command "project agent create" --kind input
bin/woobe server-schema --command "project agent create" --api-url https://woobe.example
bin/woobe completion bash
```

Discovery covers all executable handlers and flags; local schemas describe invocation and transport/runtime output. Use the server schema to discover the actual DTO. Domains remain validated and authorized by the server.

## Context and credentials

```sh
woobe context create minha-woobe --api-url https://YOUR_WOOBE_API
woobe context use minha-woobe
woobe auth login --cli-key
woobe project agent list
```

Paste the key at the masked prompt; do not put it in arguments. The CLI validates
it against this connection, discovers its Workspace and selects a single eligible
Project automatically. For several Projects, choose by name/number. Switch later
with `woobe context project select` or `woobe context project select production`.
No Project grants means Workspace-only authentication. No UUIDs or environment
variables are required. Linux/macOS store credentials in private files; Windows
uses the current user's Credential Manager. Reopening the terminal retains the
connection. Each named context has its own key and selected Project.

For automation, pipe a secret from your secret manager into
`woobe auth login --cli-key --stdin --select-project production --no-input`.
Without a selection, multiple Projects produce `project_selection_required`.
`woobe auth status` inspects the current key and scope;
`woobe auth logout --cli-key` clears local authentication without server revocation.
Changing the API URL requires login again. Runtime Keys remain separate.

Precedence: explicit flag, corresponding `WOOBE_*` environment variable, selected context, documented default. `WOOBE_CONFIG` selects the config file. Scope variables are `WOOBE_WORKSPACE_ID` and `WOOBE_PROJECT_ID`. Credentials may be imported from stdin on all supported systems; environment fallbacks are `WOOBE_CONTROL_KEY` and `WOOBE_RUNTIME_KEY`. Runtime never falls back to an administrative key. Secret values have no command-line flag.

Select a different Workspace and the previously selected Project is cleared by `context set`. Context references are local preferences; the server resolves and verifies resource ownership. Direct known resource IDs can be read without first listing every Project.

Human login accepts a JSON file or stdin containing the server's login fields:

```sh
woobe auth login --file - < login.json
woobe auth refresh
woobe auth status
woobe auth logout
```

## Configuration and publication

```sh
woobe project agent create --file agent.json
woobe project agent update AGENT --file patch.json --if-match ETAG
woobe project agent prompt create --agent AGENT --file prompt.json
woobe project agent contract create --agent AGENT --file contract.json
woobe project agent model-config create --agent AGENT --file model.json
woobe project network create --file network-metadata.json
woobe project network draft update NETWORK --file network-definition.json
woobe project agent release create --agent AGENT --file release.json
woobe project agent release promote RELEASE --agent AGENT --file promotion.json --yes
```

IDs are positional in route order, or explicit parent flags. PATCH bytes are preserved: omitted fields stay omitted; explicit null remains null. `--if-match` forwards a server ETag; it does not implement revision protection when the server ignores that header.

`--dry-run` renders a redacted request without sending it. `--yes` acknowledges the specified execution/publication/destructive action; it never changes permissions or selects another credential. No interactive prompt is used.

```sh
woobe project api-key create --file key.json --secret-file ./issued-key.json
woobe project knowledge document upload --collection COLLECTION --document-file lesson.pdf
woobe project agent export AGENT --destination agent-projection.json
```

Exports are explicitly incomplete authorized projections, not apply-ready patches. API issuance destinations must not exist. Rejected attempts leave no final file; successful issuance publishes a versioned private JSON envelope. See [test/contract and secret recovery](CONTRACTS_TEST_RECOVERY.md).

## Runtime

```sh
woobe runtime target run tutor --target-kind agent --runtime-credential runtime --file run.json --yes
woobe runtime target stream tutor --target-kind agent --runtime-credential runtime --file run.json --yes --output jsonl --timeout 10m
woobe runtime target observe tutor RUN --target-kind agent --runtime-credential runtime --output jsonl
woobe runtime target active tutor SESSION --runtime-credential runtime
woobe runtime target cancel tutor RUN --runtime-credential runtime --yes
```

Run YAML (or equivalent JSON):

```yaml
input: Explain this topic
session_id: EXISTING_SESSION_UUID
options:
  metadata:
    source: cli
```

Omit `session_id` for a new Session; reuse the returned UUID to continue. Options
accept `session_id`, `tenant_id`, `user_id`, `metadata`, `external_context`; the
previous SDK spellings such as `SessionID` remain compatible. Unknown fields,
null/empty supplied sessions and conflicting identities are rejected. Agent
Sessions follow the selected environment between Runs; Network Sessions pin their
version. Every accepted Run freezes its resolved snapshot and the compatible
backend returns `runtime_identity`. For Network targets select `--target-kind network` explicitly. Local interruption stops observation; it does not issue remote cancellation. Administrative Runs use the separate `runtime run` family. All five SDK handlers honor `--dry-run` without network execution.

## Manifest validation, plan and checkpoint

```sh
woobe manifest validate --file testdata/agent-network.manifest.json
woobe manifest plan --file testdata/agent-network.manifest.json
woobe manifest apply --file resources.json --yes --checkpoint ./apply-checkpoint.json
```

Document fields: `schema_version`, `workspace_id`, `project_id`, `steps`. Each step declares `id`, canonical `command`, positional `args`, JSON `body`, `depends_on`, optional `if_match`. Declare dependencies explicitly. Exact references such as `${steps.agent.id}` resolve persisted redacted results; interpolation inside larger strings is unsupported.

Match manifest Workspace/Project to the selected context. Preserve the same manifest and checkpoint to resume. Committed and reconciled steps are skipped; `unknown`/`in_flight` blocks execution. Never delete the checkpoint and blindly replay creation after a lost response.

The explicit-step format composes existing server operations. It is not the complete semantic resource reconciler specified in the design. `manifest diff --file resources.json` reads compatible update resources and compares supplied top-level fields. Creation existence and unresolved dependencies remain unevaluated.

For uncertain writes: `woobe manifest reconcile STEP --resource-id ID --file resources.json --checkpoint ./apply-checkpoint.json --yes`. The same manifest, origin, workspace, project and credential reference are required. An authorized GET must match nonempty supplied desired fields. Evidence proves observed state, not original-write attribution. Resume apply using the same checkpoint. Concurrent use is rejected; remove a stale `.lock` only after confirming no process uses it.

## Output and advertised extensions

The default `--output auto` shows concise text in an interactive terminal and
preserves the existing JSON envelope in pipes. `--output text` or `table` selects
relevant rows/fields. AI agents can use `--output compact`, optionally with
`--fields id,name,status`. `--wide` shows all data fields; `--output json` retains
the complete envelope. Error and collection evidence remain visible. See
[format contracts and examples](OUTPUT.md).

Proposed extension endpoints require the exact route/method in `/openapi.json`;
actual requests still require server authorization.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Internal client error |
| 2 | Invalid usage or input |
| 3 | Authentication |
| 4 | Authorization denied by server |
| 5 | Not found/inaccessible |
| 6 | Revision/state conflict |
| 7 | Connection/uncertain write |
| 8 | Deadline |
| 9 | Unsupported capability/protocol |
| 10 | Partial composed result |
| 11 | Remote Run failure/cancellation |
| 130 | Local interruption |

JSONL runtime stdout contains semantic SDK events; client errors go to stderr. Other JSON output is one envelope. Credentials and administrative secret fields are redacted; semantic runtime event payloads are preserved.

## Input validation and checkpoint inspection

```sh
woobe schema --command "manifest validate" --kind document
woobe validate-input --command "project agent create" --file agent.json
woobe manifest status --checkpoint ./apply-checkpoint.json
woobe doctor
```

`validate-input` sends only an OpenAPI GET; it does not submit the supplied body. It supports object/array/primitive types, required/properties/additionalProperties, sizes, enum/const, numeric bounds with exact rationals, RE2-compatible patterns, local references and composition. Formats `uuid` (canonical hyphenated hex, case insensitive), `date` (valid full calendar date) and `date-time` (RFC 3339, required offset, fractions and leap-second minute checks) are validated. Other formats, unsupported assertions, external references and excessive schema depth return exit 9. Advertised OpenAPI versions must be 3.1.0–3.1.2; unknown or 3.0 dialects are refused instead of interpreted as 3.1. An absent version retains the existing explicit subset. Legacy `nullable` is refused in explicitly advertised 2020-12/OpenAPI 3.1 schemas, including unused properties; use a type union or anyOf with null. `$schema` and `jsonSchemaDialect`, when provided, must select JSON Schema 2020-12 or the OpenAPI 3.1 base dialect.

Body validation applies **request direction**: a supplied `readOnly` field returns exit 2, including fields reached through references, `allOf`, nested objects and array items. Required read-only properties in the same object schema can be omitted; annotation lookup follows local references and `allOf` under that property's schema. `writeOnly` fields remain permitted and retain required/type rules. Contradictory annotations and direction annotations inside predicates (`not`, `if`, `contains`, `propertyNames`) return exit 9. Arbitrary cross-branch required/annotation projection is not inferred. Neutral internal schema checks retain their required semantics.

The same checks run in `validate-input`, `manifest preflight`, opt-in HTTP writes and opt-in manifest apply, after dependency values resolve. Invalid inputs stop before mutation and preserve `not_attempted` recovery evidence. Success reports request direction and explicitly leaves path/query validation unevaluated. The shared body validator also rejects duplicate fields, multiple JSON values and excessive input depth. Domain validation and authorization still occur on the server. Validation is explicit; writes do not silently add schema-fetch requirements.

JSON inputs reject duplicate fields, more than one value and nesting beyond 128. Manifests require object configuration bodies, exclude read steps and literal sensitive fields (including credential `value`), and reject duplicate/self dependencies. IDs match `[a-zA-Z0-9_-]{1,128}`. Canonical hashing ignores object-key order/formatting and preserves array order, null and numeric values. Updated hash/fingerprint rules can reject old checkpoints; preserve them for manual reconciliation instead of deleting/replaying.

Control Key fingerprints bind checkpoint recovery to actual key material, including environment keys. Human-session principal binding still needs authoritative server identity. `doctor` runs instance, identity and OpenAPI reads independently; partial diagnostics include evidence and exit 10. Advertised routes never imply effective authority.

## Resource projections and distribution

```sh
woobe export NETWORK --command "project network get" --project PROJECT --destination network.json
woobe export TRACE --command "project trace get" --destination trace.json
woobe manifest export --resource agent --id AGENT --destination agent.json
```

Generic export accepts canonical resource `get` operations with exact route-order IDs. Manifest shortcuts cover agent, network, skill-version, knowledge collection and surface. Every projection remains `complete:false` and `apply_ready:false`, with observed ETag/request ID when available. Unsupported Tool getters are not fabricated. Secret fields are redacted before file/output rendering. Projection export does not guarantee pagination or round-trip apply.

Packages include the executable, README, usage and `manifest.schema.json`. `artifacts.json` records version, source commit, compiler, OS/architecture, byte size and SHA256 for exactly six archives. `python3 scripts/verify_artifacts.py` verifies contents, schemas and checksums before release publication. No release/tag is created by this PR.

## Resource manifests — schema v2

```sh
woobe manifest kinds
woobe schema --command "manifest validate" --kind document --manifest-version 2
woobe manifest validate --file testdata/resources.manifest.json
woobe manifest compile --file testdata/resources.manifest.json
woobe manifest plan --file testdata/resources.manifest.json
woobe manifest apply --file resources.json --project PROJECT --checkpoint ./resources.checkpoint.json --yes
woobe manifest apply --file updates.json --project PROJECT --checkpoint ./updates.checkpoint.json --yes --skip-unchanged
```

The v2 document requires `schema_version:"2"`, `project_id` and `resources`; `workspace_id` is optional. Each resource has `key`, `kind`, explicit `action` and object `spec`, with optional `resource_id`, `parents`, `depends_on` and `if_match`. `create` forbids remote ID/ETag; `update` requires an explicit remote ID. The client never guesses identity by name or implicitly creates a missing update target.

| Kind | Supported actions | Parent / target |
| --- | --- | --- |
| Agent | create, update | update target is Agent ID; creation receives document project_id |
| Network | create, update | update target is Network ID |
| AgentPrompt | create | parents.agent |
| AgentContract | create, update | parents.agent; update target is Contract ID |
| AgentModelConfig | create | parents.agent |
| NetworkDraft | update | resource_id is its Network ID |

Whole-value references use `${resources.KEY.id}` for parent/target IDs. Referenced resource kinds must match their consumer (e.g. AgentPrompt parent must reference Agent, NetworkDraft target must reference Network). References in `spec` may address returned fields. Dependencies remain explicitly declared. Embedded interpolation and the steps namespace are rejected in v2. Actual spec DTOs/bindings still follow server contracts; the example demonstrates client composition, not a certified Network draft DTO.

Offline compilation emits a v1 execution document and hash. Both formats reuse the same diff/apply/checkpoint/reconcile machinery; semantically identical compiled plans have the same execution identity. Keep context and original resource intent stable during recovery. Explicit-ID uncertain-create reconciliation also works for v2 without replaying the creation.

`--skip-unchanged` performs an authorized GET for compatible update targets, comparing only supplied fields. Matching state is checkpointed as `unchanged`, making results available to dependent resources; resume skips that observation just as it skips completed writes. It is a recorded observation, not continuous drift detection. Changed state proceeds to the ordinary PATCH/PUT; server-side revision enforcement remains authoritative. An explicit `if_match` requires an observed matching ETag before this shortcut. Missing compatible getters (including NetworkDraft) return exit 9; default apply remains available without the option. Create intents are always explicit creations and have no name-based existence check.

Packages contain both `manifest.schema.json` (steps v1) and `resources.schema.json` (resources v2). Manifest resource coverage and semantic upsert/existence reconciliation remain limited. Portable Agent/Network YAML export/import and protected bindings use the separate Package V1 workflow below.

## Captura seletiva e paginação anunciada

```sh
woobe manifest capture --kind Agent --id AGENT --project PROJECT --field name --field description --destination update.json
woobe manifest capture --kind AgentContract --id CONTRACT --parent agent=AGENT --project PROJECT --field name --destination contract-update.json
woobe manifest apply --file update.json --project PROJECT --checkpoint update.checkpoint.json --yes
woobe request-pages /ai/agents --query project_id=PROJECT --max-pages 20
```

`capture` exige um tipo com update/get compatíveis, Project explícito e campos de primeiro nível escolhidos. Somente esses campos entram em `spec`; nulos explícitos são preservados. Identidade/contexto, segredos, campos ausentes/inacessíveis e projeções de outro ID/Project são recusados. O ETag observado entra em `if_match` quando disponível, mas a execução da condição continua sendo responsabilidade do servidor. O arquivo de destino contém um manifesto v2 bruto; stdout também informa seleção/proveniência. Isso permite editar e reaplicar a configuração escolhida; não promete exportação completa nem validação integral dos DTOs. Tool e NetworkDraft não possuem getter compatível no catálogo atual; tipos imutáveis não têm capture.

O catálogo v2 agora contém 13 tipos: Agent, Network, AgentPrompt, AgentContract, AgentModelConfig, NetworkDraft, Project, Tool, KnowledgeCollection, KnowledgeDocument, Skill, SkillVersion e ChatSurface. Project aceita apenas update e o ID deve ser o Project do documento. SkillVersion exige parent `skill` e referências de IDs do tipo Skill. As demais ações e campos seguem `manifest kinds` e o schema distribuído; não há emissão declarativa de credenciais ou categorias propostas.

`request-pages` e os comandos paginados suportam contratos revisados de cursor e histórico, além de Link. Use `--all`, `--limit`, `--cursor` ou `--before-revision` conforme o comando. A saída informa coleção inteira, páginas restantes, parcial ou não verificada; falhas preservam páginas recebidas. Consulte [PAGINATION.md](PAGINATION.md) para protocolos, limites, metadados e exemplos.

Falhas de apply agora incluem checkpoint, contagens por estado, etapa interrompida e `checkpoint_saved`. A ausência de persistência é explícita; uma resposta de sucesso não autoriza repetir uma criação. Binários empacotados incluem a revisão fonte em `version`, junto de compilador/OS/arquitetura.

## Medida de completude

`python3 scripts/completeness.py` valida a correspondência com todas as 101 entregas do §18 e verifica o relatório gerado. `docs/COMPLETENESS.md` documenta estado/evidência por item e a fórmula. Esse percentual inclui backend e E2E; não deriva de commits, número de comandos ou cobertura de código.

## Context integrity and extended schema validation

`context show NAME` resolves the selected profile. Explicit empty `--project`, `--workspace`, `--credential` and `--runtime-credential` override inherited values for that invocation. Changing Workspace clears an inherited Project unless a Project is supplied explicitly. Persist clearing with `context unset NAME workspace`, `context unset NAME project`, or `context unset NAME credential runtime-credential`; stored secrets are preserved. Attach a separate runtime reference with `context runtime-credential attach NAME --runtime-credential REF` and detach it with `context runtime-credential detach NAME`.

Changing a saved context's API URL detaches its administrative and runtime
credentials and clears inherited Workspace/Project selection. Authenticate and
attach the appropriate Runtime Key for the new API before executing a target.
Stored reusable runtime credentials are preserved; they are never transferred
automatically to the new API. Updating only a trailing slash retains attachments.

Config v1 is bounded to 1 MiB, rejects unknown/duplicate fields, dangling active context names and invalid context URLs/names, and validates before atomic replacement. See [MIGRATION.md](MIGRATION.md) for Python prototype command/credential/output migration.

The explicit `validate-input` subset additionally supports min/maxProperties, dependentRequired, dependentSchemas, propertyNames, RE2 patternProperties, if/then/else, prefixItems and contains with min/maxContains. Numeric enum/const and uniqueness use exact mathematical equality; nullable alters type acceptance without bypassing enum/composition constraints. Local JSON pointers support escaped property names, URI fragment decoding and array indices. Schema inspection includes inactive properties/branches; an unsupported rule there returns exit 9 rather than valid=true.

Limits: schema depth 64, input depth 128, shared work budget 100,000 nodes/evaluations, numeric representation at most 4,096 characters and exponent magnitude at most 4,096. Inputs exceeding evaluator bounds return exit 9. Format, external references/anchors, schema resource IDs, unevaluated-property/item semantics and unsupported assertion dialects remain outside the subset. readOnly/writeOnly and documentation keywords are annotations here, not request-direction policy. Server authorization, domain validation and create/PATCH rules remain authoritative. No automatic schema probe is added to writes.

## Body preflight, opt-in write validation and recovery integrity

```bash
woobe manifest preflight --file project.json --project PROJECT
woobe manifest preflight --file project.json --project PROJECT --require-complete
woobe project agent create --file agent.json --validate-body
woobe manifest apply --file project.json --project PROJECT --checkpoint apply.json --yes --validate-body
```

`manifest preflight` reads one OpenAPI snapshot and checks each configuration body against its advertised operation. It never executes the manifest. Body values depending on returned step fields are deferred; operation availability and supported schema declarations are still inspected. `data.complete` and `meta.complete` are false when any body is deferred or fails. `--require-complete` returns exit 9 for deferrals or a dry-run without evaluation. Invalid inputs return exit 2, unsupported contracts exit 9, with per-step evidence. Path/query schemas, authorization, resource existence and domain rules are not evaluated by body preflight.

`--validate-body` is optional and available for canonical JSON HTTP mutations and manifest apply. The default write path preserves its previous behavior. Generic request, multipart upload, SDK runtime, reads and unrelated local commands reject this flag rather than ignoring it. Validation failure marks the selected write `not_attempted`. Secret emission reserves its destination only after validation succeeds. Dry-run never fetches a schema or sends a write.

For manifest apply, one OpenAPI snapshot is fetched after local/context/checkpoint checks. Each pending body's references are resolved, then validation runs before unchanged-state observation or `in_flight` checkpointing. A failure records a resumable `not_attempted` state with a structured cause and partial report (exit 10), preserving earlier committed steps. Unknown/in-flight HTTP attempts still block resume until explicit reconciliation. Validation of a future dependent body cannot be guaranteed before its required values exist.

Validation reports include `schema_sha256`: SHA-256 of the parsed OpenAPI document serialized as sorted-key JSON with preserved numbers. Supply that digest with `--schema-sha256 DIGEST` to `validate-input`, manifest preflight, or a write/apply using `--validate-body`. A different snapshot returns exit 6 before the selected write. This identifies a client snapshot; it is not a server revision lock and does not freeze the server between discovery and mutation. The explicit supported subset and all documented schema limits still apply.

Checkpoint reads are bounded to 32 MiB. Resume/reconcile validates step IDs, result ownership, reconciliation state, saved results for terminal steps and completed dependencies against the same manifest. Returned numbers are preserved exactly through checkpointing and body references. Corrupt/incompatible checkpoints are refused; status remains an offline inspection tool. `not_attempted` can be retried by apply after correcting the prerequisite without replaying committed steps.

HTTP responses reject duplicate fields/nesting ambiguity. Canonical resource IDs must be unambiguous single segments; decoded path traversal, separators, nested escapes and control characters are refused. A canonical scope query must occur once and match the selected Workspace/Project. Generic authorized HTTP still delegates resource authorization to the server.

The default administrative transport pools read connections but sends mutations over fresh HTTP/1 connections with replay disabled, including requests carrying Idempotency-Key. This trades write connection reuse for predictable single-attempt behavior; idempotency remains a server feature, not a retry instruction. Runtime SDK calls inherit this HTTP client. Replacing the HTTP transport in an embedding application requires preserving this guarantee explicitly. Checkpoint writes also enforce 32 MiB before replacing an existing file; a committed remote write followed by a failed checkpoint save remains a partial outcome requiring recovery.

State comparisons in `manifest diff`, `apply --skip-unchanged` and `reconcile` use exact decimal JSON number semantics: `1`, `1.0` and `1e0` are equal, including inside supplied objects/arrays. Large integers remain distinct without conversion to floating point. Array order, missing fields, explicit nulls and string/number types remain significant. Nested supplied objects are compared in full; this is not a recursive partial PATCH interpretation. Comparison shares a 100,000-node budget across supplied fields, supports depth 128 and numbers of at most 4096 characters with exponent magnitude at most 4096. Unsupported comparisons return exit 9; they never justify an unchanged checkpoint or reconciliation. Expected `if_match` in diff also requires an observed matching ETag. These observations do not lock subsequent server state or establish original-write attribution.

## Advertised path/query validation

`--validate-parameters` validates the selected canonical HTTP operation's path
and query values against its advertised OpenAPI 3.1 schema before the operation.
It can be combined with `--validate-body` for writes; neither changes authority.
Dry-run remains network-free and performs neither advertised validation.

```sh
woobe project agent update AGENT_UUID --file agent.json --validate-body --validate-parameters
woobe runtime agent sessions AGENT_UUID --project PROJECT_UUID --query environment=staging --limit 1 --all --validate-parameters
woobe validate-input --command 'project agent get' --validate-parameters --path-param agent_id=AGENT_UUID
woobe manifest preflight --file resources.json --validate-parameters --require-complete
woobe manifest apply --file resources.json --checkpoint apply.json --yes --validate-body --validate-parameters
```

Parameter-only `validate-input` does not require a body and explicitly reports
`body_validation: not_evaluated`. The parameter subset supports strings,
UUID/date/date-time formats, exact JSON numbers, booleans and form arrays
(repeated values for explode=true; one comma-separated value for explode=false).
Path-level parameters are replaced by operation-level declarations with the
same name/location. Local references and unambiguous nullable/composed primitive
types are supported. Canonical/server template names may differ when method and
literal path segments match exactly and identify only one advertised route.

Missing required parameters, duplicate scalar values and invalid values return
exit 2. Unadvertised parameters, unsupported serialization/types/dialects and
ambiguous templates return exit 9. Header/cookie schemas and authorization are
not evaluated by this flag. Schema digests can pin the discovery snapshot.

Manifest apply validates resolved parameters before recording an in-flight
write; failures retain `not_attempted` checkpoints. Preflight defers parameters
that depend on prior step results and records parameter/body evidence separately.
Manifest parameter validation uses each operation's context-derived query scope;
global `--query` overrides are refused because they are not propagated to steps.
Unknown server query keys are never approved by guessing their semantics.


## Workspace category definitions

`AuthorityCategory` is a Workspace-owned resource kind. A category-only resource
manifest requires `workspace_id`; `project_id` is optional. Mixed documents still
require the owning scope of every kind. Creating a definition does not issue keys
or assign authority. Editing a definition requires an explicit ID and strong
`if_match`; it does not migrate existing grants to the new revision.

```json
{
  "schema_version": "2",
  "workspace_id": "WORKSPACE_UUID",
  "resources": [{
    "key": "reader", "kind": "AuthorityCategory", "action": "create",
    "spec": {"name": "custom-reader", "scope": "project", "permissions": ["agent:read"]}
  }]
}
```

```sh
woobe manifest preflight --workspace WORKSPACE_UUID --file category.json --validate-parameters --require-complete
woobe manifest apply --workspace WORKSPACE_UUID --file category.json --checkpoint category.checkpoint.json --validate-body --validate-parameters --yes
woobe workspace authority category diff CATEGORY_UUID --workspace WORKSPACE_UUID --from-revision 1 --to-revision 2
woobe manifest capture --kind AuthorityCategory --id CATEGORY_UUID --workspace WORKSPACE_UUID --field name --field permissions --destination category-edit.json
```

The diff reads exactly the two selected immutable definitions and reports supplied
configuration fields. It does not calculate every affected assignment or apply a
migration. `--dry-run` reports that comparison was not evaluated and performs no
network requests. Permission/condition order does not create a change; an absent
restriction and an empty restrictive set remain distinct. Unknown condition
semantics are unsupported rather than silently compared as understood authority.

Capture copies only selected fields and the observed ETag. Category specs exclude
assignment, grant, identity, status and revision fields; scope is immutable during
update. Server OpenAPI advertisement is checked before category writes. A saved
successful checkpoint resumes without another create; a lost checkpoint does not
make category creation idempotent or infer existence by name. Full uncertain-write
reconciliation and applied-category grant migration remain incomplete.

## Protected manifest credentials

Sensitive values may use an exact object `{"$secret_ref":"NAME"}` in Tool or
provider-credential configuration. Import the value with `woobe auth credential import
--name NAME --stdin < PRIVATE_INPUT` first; lookup uses the protected store beside the
selected config. Providers are private POSIX files and Windows Credential Manager.
Environment-variable interpolation, prefixes, remote stores and step-result
secrets are not supported. The stored value is the complete field value.

```json
{"schema_version":"1","project_id":"PROJECT_UUID","steps":[
  {"id":"provider","command":"project provider-credential create","body":{
    "project_id":"PROJECT_UUID","provider":"custom","name":"Provider",
    "secret":{"$secret_ref":"provider-secret"},"metadata":{}}}
]}
```

Compile and plan preserve reference markers without resolving them. Preflight
reports `deferred_protected_credential`; `--require-complete` refuses that deferred
state. Apply resolves a private in-memory snapshot, then validates the wire body
when `--validate-body` is selected. Checkpoints bind reference names to value
fingerprints and contain no resolved values. Changed, unavailable or added
credentials refuse resume before writes; use the original snapshot to finish an
existing checkpoint. Dry-run does not resolve these values or save a checkpoint.

Successful steps resume without another write. Uncertain protected writes remain
uncertain: redacted getters cannot certify their secret values. Reconciliation
and `--skip-unchanged` refuse them. Output and checkpoint results redact resolved
values even when a response echoes them under an unrelated field. This does not
make unsupported server creates idempotent after losing a checkpoint.

## Canonical MCP permission inputs

`project tool mcp set` and `bulk` always validate `allow`, `deny` or `review`, UUID
provider identity, bounded names/list sizes, duplicate names, surrounding
whitespace and unknown fields. This check also runs for dry-run, validate-input
and resolved manifest writes; invalid inputs stop before writes. Server schemas
remain optional additional validation and authorization remains on the backend.

The backend rejects undiscovered remote tool names before applying any part of a
selective update and requires a valid MCP discovery. Bulk affects only that
provider's discovered tools. `review` keeps a tool unavailable; it does not create
a per-call approval dialog. Rediscovery preserves saved modes by remote name and
new tools start in review. Existing immutable release snapshots are unaffected.


## Portable composition

Use `woobe package validate`, `plan`, `import`, `status`, `resume`, `cancel`, and
`export agent|network` for complete native author definitions. A Package requires
the matching backend capability catalog; it does not fall back to Manifest.
`--destination` optionally overrides the export directory (default: ./normalized-resource-name), while `--output` selects text/JSON/JSONL. Export accepts a name or UUID; `--env` defaults to draft, staging/production resolve current versions, and release requires `--version`. Import checkpoints are automatic unless explicitly specified. Use `package bindings SOURCE` for a destination YAML template.

Project, operation and registry UUIDs accept either letter case. For example,
`package status OPERATION_UUID --project PROJECT_UUID` also accepts uppercase
UUIDs, including when recovering with `--checkpoint`. Opaque identifiers,
aliases and idempotency keys retain their exact spelling.
Knowledge can be rebuilt from portable documents or resolved through an external
binding. See [PACKAGES.md](PACKAGES.md) for flags, lifecycle, protection, recovery
and the supported CLI/server pair. Existing resource projections and Manifest
semantic-upsert limitations remain described above.

## YAML and JSON request input

Every API command that consumes `--file` accepts YAML (`.yaml`/`.yml`) or JSON.
The wire contract remains JSON. For stdin, choose the format explicitly:

```sh
woobe agent update UUID --file ./agent-change.yaml --validate-body
woobe validate-input --command "project agent update" --file ./agent-change.yaml
woobe agent update UUID --file - --input-format yaml
```

Use `--input-format json` to require JSON regardless of the filename. Auto mode
uses the extension, then JSON object/array syntax, otherwise YAML. One document
is accepted; duplicate fields, anchors, aliases, merge keys, custom tags and
non-finite numbers are rejected before submission. Explicit `null`, omitted
fields and exact numeric values retain their meanings. A YAML API payload is
not a portable Package: use `package import` for dependency-aware bundles.
Manifests can also be written in YAML with the existing manifest schema.
No project configuration file is required for request input or command help.

## Optional local development registry

`woobe init --agents codex --root .woobe --context local` creates or reuses `.woobe-config` in the
current directory. This YAML file identifies the registry and records resource
UIDs, kinds, logical keys, aliases and paths relative to the artifact root.
Keep it in Git. `.woobe/.state/` and `.woobe-lab/` are private and ignored by Git.
Repeating init preserves registry identity/resources and can add assistants.
See [project setup](PROJECT_SETUP.md) for instruction blocks, layouts and recovery.

```yaml
schema_version: 1
registry_id: 71e7c0ee-ea31-48b9-a566-ad713b4b8407
context: local
root: .woobe
defaults:
  pull_environment: draft
resources:
  - uid: fae665bb-0817-4834-903e-3352815e9367
    kind: Provider
    key: openai-main
    alias: openai-main
    path: providers/openai-main
```

`woobe config show` displays this configuration. `woobe config check` validates
registered descriptors and their dependency graph offline; it does not evaluate
server permissions or execute mutations. `woobe resources list` lists the
registry, while `woobe resources used-by provider "@openai-main"` shows direct
and indirect local consumers, including embedding Models and Knowledge.

Provider descriptors use `provider`, `credential_ref` and optional public
`base_url`, `compatibility` and `provider_family` fields. Credential material
belongs in the existing provider/auth workflow. Managed Model descriptors may
use `provider_ref` to identify a registered Provider. Multiple Models can share
a connection; two connections remain distinct registry resources.

Development commands discover the nearest `.woobe-config` from the current
folder, stopping at the Git repository boundary. `--project-config PATH` selects
an explicit file; `--no-project-config` disables discovery. API requests,
authentication, contexts, runtime calls and standalone packages do not load this
file. Their operation is unaffected by a missing or malformed project config.

## Pull, edit YAML, push Draft

Managed development requires a Woobe server advertising `sync` and `registry`
capabilities. The server validates the complete dependency graph and authorizes
both the root and each reused artifact. Native UUIDs are retained for Agents and
Networks; changed shared dependencies use explicit copy-on-write effects.

```sh
woobe init --context local
woobe agent UUID pull --alias support
woobe agent "@support" diff
woobe agent "@support" validate
woobe agent "@support" push
woobe network UUID pull --alias helpdesk
woobe network "@helpdesk" push
```

Edit the registered `agent.yaml`, `network.yaml` and dependency descriptors in
between pull and push. Generated descriptors use block YAML with two-space
indentation and literal blocks for multiline instructions:

```yaml
format: woobe-package
schema_version: "1.0"
kind: Agent
metadata:
  key: support
  name: Technical Support Specialist
spec:
  behavior:
    additional_instructions: |-
      Establish observable symptoms first.
      Separate symptoms from root cause.
```

This excerpt illustrates formatting; the complete descriptor retains all fields,
references, exact numbers, nulls and empty collections. Strings requiring escaped
line separators remain quoted to preserve their content. Registered `.json` paths
remain indented JSON, including after pull and clone. Moving between YAML and JSON
converts only the descriptor; declared support files and resource identities stay
intact. Format-only edits do not produce semantic changes in `diff`.
Existing author files are reformatted when pull successfully writes them; review
local edits with `diff` first. Portable exports keep their server-issued lock and
downloaded bytes; editing them requires a new artifact/lock for locked validation.

Reference-first `sync` aliases `pull`, and `update` aliases
`push`: `woobe agent UUID update --path ./.woobe/agents/support`. Canonical API
`woobe agent update UUID --file patch.yaml` still accepts a raw request payload.
Quote aliases in PowerShell (`"@support"`). UUID, exact remote name on the first
pull, typed alias and registered folder are supported. Inside a linked folder,
`woobe agent pull`/`push` can omit the reference.

Pull defaults to Draft. `--env staging` and `--env production` select the current
native snapshots; `--env release --version 1.2.0` selects an immutable release.
Regardless of the pulled environment, push writes Draft. Publishing and
activation remain explicit lifecycle operations. `--path` is an optional folder
inside the configured artifact root; local resource identities stay in
`.woobe-config`, destination UUIDs and base revisions stay in `.state/`.

`diff` and `status` are offline and include dependency and declared support-file
changes. `validate` checks the compiled portable schema offline; server semantic
validation, credentials and authorization are checked during push. `--dry-run`
never applies a push; it uploads and validates the exact server plan and reports every native effect for the registered dependency closure.

Pull performs a three-way merge against the last remote base. Independent edits
merge; conflicting fields or support files leave all author files and state
untouched. Push includes native revision evidence, so stale edits receive a
conflict instead of overwriting another client. Pull again, resolve the listed
paths, inspect diff and retry. Resetting or deleting local state is unnecessary.

Networks preserve repeated nodes separately. An Agent Draft is editable, while
fixed constituent snapshots remain under `snapshots/` with separate UIDs. Editing
a frozen constituent is rejected; pull its standalone Draft to edit the Agent.
A Network push does not activate constituent Agents as standalone Production.

Local writes use a registry process lock and a durable transaction journal.
Interrupted transactions recover on the next development command, and recovery
refuses to overwrite a conflicting external edit. Push checkpoints pin the
content, destination and principal. If acceptance is unknown, the next push
looks up the same operation rather than sending another mutation. Keep `.state/`
until the operation has been reconciled; it is intentionally excluded from Git
and from compiled packages.


### Explicit local identities and recovery

```sh
woobe resources create provider primary --file ./provider.yaml
woobe resources create model chat --file ./model.yaml
woobe resources create agent support --file ./agent.yaml
woobe agent '@support' create --yes

woobe resources clone agent '@support' --alias support-v2
# Edit the clone's YAML; its Provider, Model, Tool and Knowledge refs are shared.
woobe agent '@support-v2' create --yes
woobe resources move agent '@support-v2' --path agents/new-location
woobe resources alias agent '@support-v2' --alias support-next

woobe resources register tool lookup --path tools/lookup/tool.yaml
woobe resources unregister agent '@support-next'
woobe resources prune --dry-run
woobe resources prune --yes
woobe resources diff
woobe resources validate
woobe resources push --dry-run
woobe resources push --yes
woobe agent '@support' reconcile
```

If you delete artifact folders manually, `.woobe-config` still registers their
paths. `config check` names the missing descriptor. Restore the files when the
deletion was accidental. To keep the deletion, `resources unregister KIND
'@alias'` removes one entry, including an absent descriptor. For multiple deleted
artifacts, preview with `resources prune --dry-run`, then use `--yes` to unregister
only absent descriptors. The remaining graph must have valid references: a
deleted Model still used by a present Agent cannot be pruned. Unreadable, corrupt,
linked or oversized files are rejected rather than treated as missing. These
commands retain present author files and private bindings and never delete
remote resources. Do not delete `.state/` to repair a stale registry.

`resources create` copies a supplied author descriptor with a new UID. For
support files, register an existing folder or clone a registered artifact.
`create` on a managed Agent/Network is the explicit remote creation step and
rejects an already bound root. `push` updates a bound Draft and never creates
another root. Names do not determine native identity. Clone retains dependency
refs, gives the selected root a new UID and uses the new alias as its display
name; edit metadata.name before creation for a different name. Its native identity
is unbound.
A moved artifact retains UID, logical refs and native bindings. Only declared
files move, through a recoverable transaction; unrelated files stay in place.
Unregister refuses consumers and retains author files and private native bindings;
it never deletes an Agent, Network or shared dependency from Woobe.

Bulk operations visit only registered Agent/Network roots in dependency order;
frozen Network constituents are not independent roots. Creation remains explicit.
Bulk push stops on the first error and reports completed results and remaining
roots. Each accepted write retains its own content-bound checkpoint.

After a timeout or interrupted push, `reconcile` observes the original operation,
even with broken local YAML. It cannot upload, plan or apply again. Unknown
acceptance remains pending. Terminal success refreshes native bindings and the
accepted local base. Terminal failure/cancellation reconciles only components
with matching approved definition digests and completed owner receipts, then
allows an explicit new attempt. Local edits made after the original upload remain
unsynchronized; no author file is overwritten during reconciliation.

### Native lifecycle with local references

Lifecycle commands use saved native snapshots. Push YAML edits first; staging or
publication does not upload local changes implicitly.

```powershell
woobe agent '@support' push
woobe agent '@support' stage --yes
woobe agent '@support' test --file ./support-test.yaml --yes
woobe agent '@support' publish --notes "Reviewed support changes" --yes
woobe agent '@support' activate --version 1.2.0 --notes "Deploy approved release" --yes
woobe agent '@support' rollback --version 1.1.0 --notes "Restore previous behavior" --yes
woobe agent '@support' release list
woobe agent '@support' get
woobe model usage '@chat-model'
woobe provider usage '@openai'
```

Native UUIDs work without a development config. Explicit `@alias` and local
paths use bindings scoped to the selected connection, Workspace and Project.
The canonical forms (for example `agent release promote UUID RELEASE_UUID
--file promotion.yaml --yes`) remain available with JSON or YAML input.

### Execute and record a release test

`agent REFERENCE test` executes the saved Staging snapshot by default. It records
the actual answer, parsed output, Run identity, latency and validation errors in
Woobe. Use `--env draft`, `--env production`, or `--env release --version 1.2.0`
to select a different saved snapshot. The same UUID, alias and path resolution
applies. Both Agent versioning and Run execution permissions are required.

```yaml
# support-test.yaml
message: "Explain how to reset my password"
# Optional exact assertion against parsed output, or {answer: ...} for text:
# expected_output:
#   answer: "The exact expected answer"
# external_context:
#   customer_tier: premium
```

```powershell
woobe agent '@support' test --file ./support-test.yaml --yes
woobe agent UUID test --env release --version 1.2.0 --file ./support-test.yaml --yes
woobe agent UUID release tests SNAPSHOT_UUID
```

Failed execution or assertion exits with code 6 and includes the recorded test
result. A network timeout is not retried automatically. The older `agent release
test` operation only registers a test record; `agent REFERENCE test` and the
canonical `agent release run-test` perform the actual execution.

A captured Skill binding retains both the Skill namespace and its immutable
version. Knowledge bindings retain both Collection and Vector Snapshot identities:

```powershell
woobe skill version list '@procedure'
woobe skill version get '@procedure'
woobe knowledge collection get '@policy'
woobe knowledge snapshot list '@policy'
woobe knowledge snapshot get '@policy'
```

Parent commands select the namespace/Collection; version/snapshot commands select
the captured immutable identity. Old bindings without parent evidence require a
fresh pull. Identity is never inferred from a matching display name. Explicit
`--context` and `WOOBE_CONTEXT` take precedence over `.woobe-config` preferences.
A Skill clone changes its `SKILL.md` frontmatter name as well as its descriptor,
so importing the clone creates a distinct native Skill namespace.

### Network lifecycle and native archive

```powershell
woobe network '@helpdesk' stage --yes
woobe network '@helpdesk' publish --yes
woobe network '@helpdesk' activate --version 1.2.0 --notes "Reactivate approved composition" --yes
woobe network '@helpdesk' rollback --version 1.1.0 --notes "Restore stable composition" --yes
woobe agent '@support' archive --yes
woobe agent '@support' delete --yes
```

Network staging/publication requests a native preview, approves only its content
bound action IDs and sends the Draft revision or current Staging identity back
as a precondition. Concurrent changes fail instead of selecting a newer snapshot.
Network publication follows Woobe's existing behavior: create/reuse an immutable
Release and activate the Network in Production. Constituent Agent Releases do
not activate standalone Agent Production. Activation/rollback select a saved
immutable Network version and guard the current Production pointer.

Agent `archive` and `delete` use Woobe's native archival operation. Historical
snapshots and runs remain available for audit; no shared Model, Provider, Tool,
Skill or Knowledge is deleted. The CLI reads the native revision and sends
`If-Match`; an explicit `--if-match` remains authoritative. Native dependency
checks can block archival while Networks or Chat Surfaces still depend on the
Agent. `resources unregister` is a separate local registry operation.

For isolated remote authoring, use `woobe agent '@support' draft open hotfix --from
production`, then `draft push`. Networks support the same flow. These operations
save closed objects without publication/activation; see [ASaC](ASAC.md) for exact
checkpoint registration and recovery. They are separate from native Draft push.

Restore a local source checkpoint with `woobe agent '@support' checkout --revision REVISION_ID`
(or `woobe network`); see [ASaC](ASAC.md#restore-local-author-source). This protects
uncheckpointed edits and changes only local files, not a remote environment.

Use `woobe agent '@support' rebase --onto REVISION_ID` to reconcile sealed local
branches, and `revision merge REV_A REV_B --message 'Resolved content'` to seal
manually resolved files with both parents. These operations preserve old revisions
and do not contact the backend; [conflict behavior](ASAC.md#reconcile-sealed-local-branches)
is explicit and never bypassed by `--yes`.

Recover an existing isolated Draft selection after a clone with
`woobe agent '@support' draft select NAME_OR_UUID` or the Network equivalent.
`--dry-run` reads its identity/generation without saving private selection state.
This preserves author files and remote resources; it does not hydrate native
bindings or secrets. See [ASaC recovery](ASAC.md#isolated-remote-drafts).


Fetch isolated revision metadata without touching local author files:

```sh
woobe agent @support history fetch --revisions
woobe network @support history fetch --revisions --dry-run
```

Requires CLI 0.20.0+ and a backend advertising `asac.revision_catalog`.
This does not download executable/source objects or change the working head.
See [ASaC](ASAC.md) for the distinction from release/deployment history.

Remote revision hydration also retains exact author objects when advertised by the backend. Checkpoint uploads source custody first; hydration recompiles the recovered source against the sealed definition. Working files only change through a separate guarded checkout. See [ASaC](ASAC.md).

### Stage a sealed isolated Agent or Network revision

```sh
woobe agent '@support' stage --revision REVISION_ID --dry-run
woobe agent '@support' stage --revision REVISION_ID --yes
woobe agent '@support' candidate CANDIDATE_UUID
woobe network '@helpdesk' stage --revision REVISION_ID --yes
woobe network '@helpdesk' candidate CANDIDATE_UUID
```

Use actual checkpointed revision/Candidate IDs. This reads the verified retained
object and checks the selected remote Draft generation; current YAML edits are
not uploaded. Acceptance is asynchronous preparation, without publication or
environment selection. Lost responses use `draft reconcile`, preserving the
original operation. See [ASaC](ASAC.md#prepare-an-exact-immutable-candidate) for
checkpoint prerequisites, status, bindings and recovery.

## Exact Candidate evaluation

After an isolated `stage --revision`, inspect the Candidate until its state is
`ready`. Evaluate its UUID with a versioned YAML suite; current local YAML and
native environment selections cannot replace this frozen snapshot.

```yaml
schema_version: '1.0'
suite_id: support-smoke
suite_version: '1'
dataset_version: '1'
policy_version: all-cases-pass@1
cases:
  - id: greeting
    message: Hello
    # Optional: expected_output is compared to actual structured output,
    # or {answer: ...} for unstructured text. Omit it for execution/schema checks.
```

```sh
woobe agent '@support' test --candidate CANDIDATE_UUID --file suite.yaml --yes
woobe network '@helpdesk' test --candidate CANDIDATE_UUID --file suite.yaml --yes
woobe agent '@support' evaluation EVALUATION_UUID
woobe network '@helpdesk' evaluation EVALUATION_UUID reconcile --yes
```

The suite accepts 1–16 uniquely named cases. Suite, dataset and policy versions
are declared identities; the backend separately verifies content digests. Every
case gets its original native Run identity before execution. Qualification uses
actual terminal Run evidence, exact snapshot identity, output validation and
current binding fingerprints. Missing evidence stays incomplete. Failed cases
exit with code 6; `accepted` and `running` do not mean passed.

The immutable acceptance receipt identifies the evaluation. Inspect its ledger
for the current result. If acceptance is uncertain, use `draft reconcile` before
another write: it recovers the original receipt and never executes a case again.
The evaluation's own `reconcile` reads original Run evidence without provider
calls. Neither command publishes nor changes Production. Do not combine
`test --candidate` with `--env` or `--version`. Native Agent `test --env` remains
available; Network testing requires an exact Candidate. Inspection by native UUID
works without `.woobe-config`; accepting an evaluation uses private project state
to preserve its write identity. Exact Candidate evaluation requires CLI 0.25+
and a backend advertising `asac.candidate_evaluation`.

Exact Network publication uses `--candidate UUID --evaluation UUID --notes REASON --yes` and preserves Production. Inspect or explicitly resume/cancel with `network UUID publication PUBLICATION_UUID [reconcile|cancel]`. See [the complete recovery flow](ASAC.md#publish-and-recover-an-exact-network-candidate); legacy publication without `--candidate` retains its activation behavior.

Workflow reservations use `woobe agent '@support' lease acquire --scope draft`
(and Network equivalents). Renew/release present privately retained workflow
proofs; `lease reconcile` recovers original acceptance without another mutation.
See [ASaC workflow reservations](ASAC.md#bounded-workflow-reservations) for scope,
expiry, native UUID flags and administrative break.

Exact Release selections use `agent|network REFERENCE deployment plan` with an
explicit Release, expected environment generation and audit reason, followed by
a short environment lease and `deployment apply PLAN_UUID --yes`. Recover lost
responses with `deployment reconcile`; see [ASaC](ASAC.md#exact-release-deployment-plans).

Project lifecycle administration uses YAML and explicit generation CAS: see [Project lifecycle policy](PROJECT_LIFECYCLE.md). These commands work without a development registry and cannot grant resource permissions.

Server-signed ASaC receipts can be exported and verified offline with an explicit
operator-confirmed root. See [signed receipts](SIGNED_RECEIPTS.md) for trust pinning,
rotation, revocation and limits on freshness and Git provenance.

## Trusted pipeline provenance

For an existing publication, use offline `git-proof` and an independently
authorized `git-attest` operation. See [the complete workflow](GIT_PROVENANCE.md).

Synchronous Runtime JSON preserves exact integer identities and generations, including values above the floating-point integer limit. Responses are bounded to 16 MiB; SDK authentication and failure semantics remain in effect.

## Unified delivery

See [Deployment](DEPLOYMENT.md) for exact Release/Staging/local delivery, private intent recovery and explicit rollback. See [CI deployment](CI_DEPLOYMENT.md) for deploy-only authority and encrypted checkpoints. Existing commands retain their semantics.

## Contract and timeout recovery

See [references, validation and private recovery](CONTRACTS_TEST_RECOVERY.md) for exact Prompt/Contract capture, Contract PATCH concurrency, failed test exits, recoverable native test UUIDs and issued-secret stdin import.
