# Portable packages

## Assistant npm package versus portable packages

`woobe skill install` installs embedded coding-assistant instructions offline;
`woobe-cli-skill` is an optional compatible npm installer. It is not a
Woobe portable package or runtime Skill. This guide describes Agent/Network
composition transfer; [AGENT_SKILL.md](AGENT_SKILL.md) describes npm installation.

Package V1 is implemented in woobe-cli and Woobe PR #179. These commands require the matching Package capability/schema catalog;
the stable CLI's Manifest commands remain independent.

## Quick workflow

Use the selected connection/project; authenticate with `woobe auth login --cli-key`.
Names and UUIDs are accepted for Agent and Network export. Names must match exactly;
ambiguous names require a terminal choice or an explicit UUID with `--no-input`.

```powershell
woobe package export agent "Orders & Requests Agent"
woobe package export agent 01a00d4a-fa75-7629-a2c6-773c25c6e2ef
woobe package export agent AGENT_UUID --env staging
woobe package export agent AGENT_UUID --env release --version v1.0.20261007.01
woobe package export agent AGENT_UUID --env production
woobe package export network "Customer Support" --env production
```

The default is the current **draft**, never production. Staging/production resolve
current assignments inside the server's frozen capture; release resolves the exact
`--version`. An unavailable environment/version fails without fallback. Names/versions
of the package are derived from captured author metadata. Unversioned definitions use
`0.0.0+<portable-definition-hash>`. `--package-version` overrides package metadata;
`--version` selects a release with `--env release`. Legacy `--source`/`--snapshot-id`
remain compatible, including their old `--version` package metadata meaning.

`--destination` defaults to `./normalized-resource-name`, even when exporting by
UUID. Paths are safe on Linux, macOS and Windows and existing paths are never replaced.
`--name` optionally overrides package metadata and its default directory name.
Exported `woobe.yaml` and component descriptors are readable YAML, with multiline
prompts. YAML and JSON descriptors are accepted. Operational plans/checkpoints/locks
remain JSON. By default a present lock is verified, including without `--locked`.
That flag additionally requires a lock; omitting it never authorizes changing
sealed bytes. Use the separate editable-copy workflow below.

```powershell
woobe package validate ./orders-requests-agent --locked
woobe package bindings ./orders-requests-agent --destination ./destination.yaml
# Fill every placeholder using destination identities/private references.
woobe project provider-credential list
woobe package plan ./orders-requests-agent --bindings ./destination.yaml --save-plan ./plan.json
woobe package import --plan-file ./plan.json --wait
# Or plan and apply directly:
woobe package import ./orders-requests-agent --bindings ./destination.yaml --wait
```

If no destination requirements exist, omit `--bindings`. Keep bindings and saved plans
outside the portable package directory. SOURCE accepts a directory, its `woobe.yaml`,
or a `.tar.gz`/`.tgz` archive. The generated bindings template is incomplete until filled;
credentials and secrets are never included in portable author data. The template uses
`vector_snapshot_id` for external knowledge and `protected_ref` for private values.

Imports **create** resources in draft by default, regardless of export origin.
Checkpoints are automatic under the private CLI config directory's `package-imports/`.
They are scoped to API/project/principal/input/lifecycle. Repeating the same command
reconciles the original operation, even after completion, without another Apply. Use
an explicit new `--checkpoint` for an intentional second import. Output includes the
checkpoint path for `package status --checkpoint PATH --wait`. Automatic Windows
state uses an explicit private inheritable DACL; existing directories are checked.

For focused assistance use `COMMAND --help` or `woobe help package export agent
--output compact`. `--output` selects terminal formatting; `--destination` selects
an artifact path. Use `--wide` or `--output json` for full metadata and inventory.
`woobe agent export` and root `export` still return partial JSON projections; use
`package export` for portable YAML composition.

Validate a declared closure locally, without loading config, credentials or HTTP:

```sh
woobe package validate ./support
woobe package validate ./support --locked
# Check an edited copy without claiming the captured bytes still match:
woobe package validate ./support --structure-only
```

Plan with an existing credential binding:

```sh
woobe package plan ./support --project PROJECT_ID \
  --bind credential.primary-key=CREDENTIAL_UUID \
  --save-plan ./approved-plan.json
```

Use `--bindings destination.yaml` for an `ImportBindings` document. Each declared
alias must have exactly one destination binding. `--bind credential.ALIAS=UUID`
is repeatable, but duplicate aliases are errors, including aliases already
present in the bindings file. Protected references are not resolved by planning.
The approved plan receipt is private and is created exclusively: an existing
file is never overwritten, including when `--yes` is provided.

```sh
woobe package plan ./support --bindings destination.yaml --dry-run
```

Dry-run captures and validates local bytes and binding coverage. It never opens a
credential store or contacts the API. It reports server semantics/authorization
as unevaluated, and cannot save a server-approved plan or validate remote schemas.

`--validate-body` validates the actual planning JSON against the advertised
OpenAPI request-body contract before submission. `--validate-parameters` validates
the upload and plan path/query schemas. `--schema-sha256` can pin that OpenAPI
snapshot. Binary multipart upload validation remains server-owned.

Planning defaults to `--lifecycle draft`. `release` and `production` require
`--release-notes`; `production` also requires `--reason`. The total `--deadline`
defaults to five minutes and includes upload, planning and HTTP requests.

Observe already accepted operations with `package status OPERATION_ID`, optionally
`--wait --deadline 5m`. An accepted operation is not complete. `package resume
OPERATION_ID --revision REVISION` resumes its observed dependency wait;
`package cancel OPERATION_ID` requests cancellation without deleting shared
resources. Package polling only retries transient GET observations, never POST
mutations.

Apply a captured source or an approved private plan with an optional explicit checkpoint:

```sh
woobe package import ./support --project PROJECT_ID \
  --bind credential.primary-key=CREDENTIAL_UUID \
  --checkpoint ./import-checkpoint.json --wait --wait-timeout 5m
woobe package import --plan-file ./approved-plan.json --project PROJECT_ID \
  --checkpoint ./import-checkpoint.json --wait
```

Source imports also save `CHECKPOINT.plan.json` exclusively so a prepared request
can use its original approved plan after restart. The checkpoint stores identities,
revisions and state, never authorization or resolved protected values. Protected
binding aliases are read once immediately before the single Apply request. The
in-flight checkpoint is fsynced before POST. A lost response is an unknown
outcome; invoking import with the same checkpoint performs lookup/observation
without posting Apply again or rereading protected bindings. A lookup 404 does
not authorize a second Apply. Existing private operational files are not replaced
by `--yes`.

Native lifecycle phases preserve standalone Agent Production when a Network
creates Agent Releases. Qualification covers all four native lifecycles, complete
cross-project Agent/Network roundtrips, protected HTTP bindings, fresh MCP discovery
and portable Knowledge rebuilt in the destination. Runtime execution uses a separate
key after all local package directories have been deleted. The
[acceptance matrix](https://github.com/A1b3rt0M3rcad0/woobe/blob/feat/portable-package-import-export/docs/testing/PACKAGE_ACCEPTANCE.md)
maps T01–T26 to the executable gates; exact paired results are in VALIDATION.md.

Export a captured native definition with all declared support files:

```sh
woobe package export agent AGENT_UUID --source staging \
  --destination ./support --name support --version 1.0.0
woobe package export network NETWORK_UUID --snapshot-id SNAPSHOT_UUID \
  --destination ./network --name network --version 1.0.0
```

Use exactly one of `--source draft|staging|release|production` or `--snapshot-id`.
The server freezes the source once. Download verifies transport bytes, exact
inventory and artifact digest, then publishes the complete locked destination
without replacing any existing path. `--knowledge portable` is the default;
`--knowledge binding` exports a destination requirement and reports that the
package is not self-contained. Authentication values, OAuth state, discovered
MCP schemas and destination IDs are never portable author configuration.

Per-capability MCP permissions preserve native `risk` labels, including `unknown`
and custom classifications. A risk is nullable or a string of 1–256 characters;
its label does not change the `review`, `deny` or `allow` permission. The CLI and
backend must use the same generated schema catalog. Updating only one side of a
catalog change will fail compatibility checks; `woobe package doctor` reports
both digests without bypassing validation.

An existing operation can be observed or controlled using only its checkpoint:

```sh
woobe package status --checkpoint ./import-checkpoint.json --wait
woobe package resume --checkpoint ./import-checkpoint.json --revision REVISION
woobe package cancel --checkpoint ./import-checkpoint.json
```

Scope must still match API origin, Project and principal fingerprint. An unknown
checkpoint performs lookup with its original key; it never starts another Apply.
JSONL output has ordered progress records and one final record with the last
known remote state. A local timeout or interrupt does not cancel the operation.

POSIX operational files use mode 0600 and native exclusive locks. Windows uses
native owner/DACL checks and LockFileEx; its parent directory must already be
private so inheritance cannot expose newly created files. Unsupported or unsafe
protection fails before sending Apply. File data is synced before replacement;
Windows does not offer the POSIX directory-fsync guarantee. The six native CI
runners qualify the same Package parsing, filesystem and checkpoint tests.

Apply preserves central exit codes for server rejection, deadline (`8`) and local
interruption (`130`). An uncertain acceptance has domain code
`PACKAGE_OUTCOME_UNKNOWN`; it never permits an automatic second Apply. Polling
honors a positive server delay; otherwise it uses bounded 2–15 second exponential
backoff with jitter. A local timeout does not cancel the remote operation.

## Editable copies and new seals

```sh
woobe package edit ./captured --destination ./author
# Edit the YAML in ./author.
woobe package validate ./author
woobe package seal ./author --destination ./sealed
woobe package validate ./sealed --locked
```

Both commands are offline and accept a directory, manifest or archive source.
`edit` requires a valid sealed source; the separate author copy omits the original
lock. `seal` creates a new captured inventory from validated author bytes. Parents
must exist; destinations must be new. `--dry-run` validates input without creating
a copy. The original is preserved, and a corrupted sealed source is rejected.
Author validation is structural: semantic checks and destination bindings remain
the backend plan's responsibility. For updating an existing Agent/Network, prefer
managed pull/edit/push rather than importing a new resource.

## Structural validation versus capture integrity

`package validate --structure-only` checks the current descriptors, reference
closure, support files, path confinement and limits without reading or comparing
`woobe.lock.json`. It accepts directories, `woobe.yaml` and tar.gz. Transport
checksum, archive traversal/link/duplicate protections remain enforced.
The result includes `validation_mode: structure_only` and
`capture_integrity: not_evaluated`, in text, compact and full JSON. `valid: true`
therefore means structurally valid current author data, not an intact capture.
Server semantic validation and destination authorization still require a plan.

Default validation verifies a present lock and reports `capture_integrity:
verified` or `absent`. `--locked` additionally requires a lock. `--structure-only`
and `--locked` are mutually exclusive. Planning, import, edit and seal do not
accept the structural-only flag and keep their existing integrity checks.
Validation never updates, removes or repairs a lock. Use the verified `edit` →
edit author → `seal` flow for a new portable artifact; keep the captured original.

The retest's comment edit with an old lock remains an integrity error under
`--locked` or default validation; the explicit structural mode succeeds if the
current package is otherwise valid. Invalid schemas/references still fail.
An installed assistant reference is a versioned local copy: after upgrading the
CLI, inspect `woobe skill status --agent codex-legacy` and update it with
`woobe skill install --agent codex-legacy` from the intended project directory.
The installer preserves local edits; review reported drift rather than forcing
an overwrite. Codex's current preset is `codex` (`.agents/skills`); use the legacy
preset only for a skill under `.codex/skills`.

## Missing Network bindings and legacy snapshots

`ASAC_CANDIDATE_BINDING_UNAVAILABLE` identifies the component descriptor and
`/metadata/key`. A canonical Network create plus pull captures source but does
not establish every accepted registry identity. Inspect
`woobe network '@network' bindings recover --dry-run`, verify destination
Provider bindings, and establish the accepted closure with managed `push`.
Update the isolated Draft, create/checkpoint its revision and stage that exact
revision. Do not repeat an uncertain accepted write; reconcile its operation.

A `PACKAGE_EXPORT_NETWORK_CONSTITUENT` node path identifies an incomplete exact
Agent capture. A suffix such as `/spec/model/primary` identifies the missing
ModelSpec; inspect that node's selected Agent/snapshot. A mutable Draft can be
reconfigured and saved through native Agent authoring, then explicitly rebound
in a new Network Draft. An immutable historical snapshot with missing evidence
cannot be certified by substituting the latest Model/Agent or rewriting its
hashes. Keep the original, prepare/evaluate a complete new Candidate and publish
a new Release. Export again from the explicitly repaired Draft/new Release.
The CLI cannot reconstruct missing historical facts or repair an operator's
stored snapshots without access to those resources.


## Remote configuration packages (schema 2.0)

With a server advertising the matching 2.0 catalog and structural installation:

```sh
woobe package export agent AGENT_UUID --package-schema 2.0
woobe package plan ./support --structural --save-plan ./support-plan.json
woobe package import --plan-file ./support-plan.json --wait
```

The manifest declares configuration keys and Provider connections without values.
The CLI generates explicit create bindings for these declarations; it does not
adopt existing keys or connections by name. To reuse them deliberately, pass
`--bind configuration.PRIMARY_API_KEY=EXISTING_KEY` and/or
`--bind credential.primary=CREDENTIAL_UUID` when planning or importing.
An explicit bindings file must cover every requirement.

Structural installation is Draft-only and never reads local protected values,
performs MCP discovery, builds embeddings or activates a deployment. The receipt
reports installation, configuration, runtime preparation and deployment
separately. Missing values are filled by an authorized operator in Woobe →
Project → Environments. The matching capability is checked before mutation;
older servers reject this flow without falling back to local secrets.

Export defaults to the unchanged 1.0 format. Select `--package-schema 2.0` for
remote authentication declarations. Existing operational 1.0 imports preserve
their behavior; `--structural` is explicit and never silently inferred.

Package 2.0 also carries the opt-in Agent `artifacts` policy and Network
`settings.artifacts_enabled` requirement. The Agent workspace binding names a
logical namespace and a required, non-model-exposed string field in
`external_context` with its declared `run` or `session` scope. The field value
supplies the Workspace's external key and never carries a private Workspace ID.
Actions, bounded read/search/write limits and an optional pinned processing
profile (`ref` plus `revision`) travel with the definition; Workspace IDs, signed
URLs, private document content and binary assets do not. Runtime resolves the
logical binding under the authorized Project/Environment and Runtime Key;
portable import grants no Workspace access. PageIndex remains optional and
requires server capability and grants. No OpenAI API key is part of this package
requirement. Old definitions default to
disabled. An enabled capability cannot be downgraded to Package 1.0, and a
Network requiring Artifacts must include at least one Agent that enables the
capability. This authoring policy never grants Workspace access by itself;
current runtime authorization remains a server decision.

An authored Agent declares the External Context key and its visibility/scope
alongside the capability. The logical `namespace` and field name are portable;
the Runtime resolves the value for the caller.

```yaml
spec:
  external_context:
    workspace:
      schema: {type: string}
      required: true
      scope: session
      model: {expose: false}
  artifacts:
    enabled: true
    workspace_binding:
      field: workspace
      namespace: team-docs
      scope: session
    actions: [read, search, process]
    processing_profile:
      ref: pageindex-default
      revision: 3
```

The Network requirement pins the same logical binding and allowed actions in
`spec.settings.artifact_workspace_binding`. Run `woobe package validate` for
offline structure, then plan against the destination's advertised schema and
authorized bindings. A destination Runtime request must resolve the logical
Workspace through the authenticated API; package import never attaches a
Workspace ID or bypasses grants. Use `woobe artifacts upload` to transfer new
source bytes and pass the resulting exact revision in runtime `content_parts`.

HTTP group routes can declare their own remote `authentication` in schema 2.0.
Each referenced key must be declared by the manifest. Omitted route authentication
inherits the connection; explicit `none` suppresses its private headers. Protected
typed routes cannot be exported as 1.0. See [configuration](CONFIGURATION.md).

This branch is under qualification; complete preparation/resume and ASaC
integration are not yet ready for release.


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

Structural Network import keeps captured Agent content but binds destination nodes to imported Drafts (`constituent_binding_policy: imported_draft`). It does not create Staging/Release snapshots or deploy constituent Agents. Review this policy in the approved plan before applying.

Schema2 `package bindings SOURCE` produces a schema2 YAML template with explicit
`create: true` choices for declarations/connections. Review those choices or
replace them with explicit existing bindings before `package plan --structural`.
It never emits `protected_ref` placeholders for remote configuration. Knowledge
references still require an explicit destination snapshot. Managed development
also negotiates schema2; see [development](DEVELOPMENT.md#remote-configuration-in-managed-development).
