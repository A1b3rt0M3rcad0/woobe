
### Bind a Provider before the first Agent push

# Managed development

After cloning without private `.state`, use `woobe agent '@support' bindings recover`
(or Network) to verify and restore accepted native identities, then explicitly
bind destination Providers. Recovery does not establish an accepted YAML base.
See [ASaC recovery](ASAC.md#recover-native-bindings-after-cloning) for conflicts,
exact frozen snapshots and dry-run behavior.

For coding assistants, use `woobe init --agents codex` or `--agents claude`
from the project root. [Integrated setup](PROJECT_SETUP.md) installs the embedded
skill, prepares instructions and protects private state/lab files. Standalone
`woobe skill install` remains available for skill-only setup.
It follows these same development flows; it does not upload a runtime Skill or
replace the optional registry. UUID API/runtime commands still work without it.

Local descriptors use readable YAML blocks for ordinary multiline instructions.
Strings containing tabs or line separators that YAML would normalize use quoted
escapes to preserve their exact value. Do not replace those escapes with literal
indentation unless you intend to change the instructions.

Create/register a public Provider descriptor with `spec.provider` (and optional
base URL); credentials belong to the destination, never the author YAML.

```sh
woobe provider list
woobe resources bind provider '@openai-main' CREDENTIAL_UUID
woobe agent '@support' create --yes
```

Binding verifies the credential is active, belongs to the current Project and
matches the Provider type. It is stored under private `.state`, scoped to API,
Workspace and Project. Repeating the same binding is safe; rebinding or assigning
the same native credential to a second local Provider is rejected. `--dry-run`
performs the read and validation without persisting. Providers captured by `pull`
already have this binding.

## Remote configuration in managed development

`pull` negotiates Package 2.0 when Woobe advertises its ASaC definition scope and
matching catalog. Captured Provider descriptors contain typed
`spec.authentication` references, not values; native Provider UUIDs remain in
private destination bindings. Validate, push, checkpoint and Stage keep that
meaning. `push` updates Draft structurally; Candidate preparation, evaluation and
deployment remain separate actions. Missing values or use grants still block
runtime execution.

Package 1.0 and its immutable history remain supported. A server without the new
advertisement uses the existing workflow. An incompatible advertised catalog is
an error, never a silent downgrade. Do not replace remote references with local
environment variables or put secrets in author files.

### Surface authoring and lifecycle

A Surface has one `spec.target_ref` to a registered Agent or Network. Pull or
create that target first and publish its Production Release. The CLI keeps the
Surface identity once created; configuration pushes preserve its frozen target
Release and never activate or refresh it implicitly.

```sh
woobe resources create surface chat --file surface.yaml
woobe surface '@chat' create --yes
woobe surface '@chat' diff
woobe surface '@chat' push --yes
woobe surface '@chat' pull
woobe resources push --kind surface --dry-run
woobe surface activate '@chat' --file empty.yaml --yes
woobe surface disable '@chat' --yes
```

For an existing native Surface, use
`woobe surface SURFACE_UUID pull --alias chat`; its target must already be pulled
in this connection and Project. Pull merges independent local/remote edits and
stops at conflicting fields. Push compares the captured timestamp and sends
`If-Match`; the server rechecks it while holding the native row lock. A target
change requires cloning/creating another Surface.

Surface settings follow their native lifecycle: configuration changes can affect
an active Surface. Disable it first when changes must stay offline. Agent/Network
pushes always target Draft. Surface bulk dry runs report identity/CAS validation;
the native API validates its payload on apply. They do not claim an executed
server package plan. Bulk traversal runs target roots before their Surfaces.

If a Surface create times out, its durable local intent blocks automatic retries.
Inspect `surface list`, then reconcile explicitly with
`surface UUID pull --alias chat`. No keys, session tokens or access secrets enter
Surface author files.

Author `target_ref` and other dependency references use stable registry **keys**,
shown by `resources list`; terminal references use `@alias`, UUID or path.
UUID letter case does not change identity; alias matching remains case-sensitive.
Changing an alias does not rewrite dependency identity. Provider bind also records its
native identity so a later target pull reuses that same Provider rather than
creating another definition.

### Create local artifacts with support files

`resources create` copies the descriptor and its declared Skill/Knowledge files
from the descriptor's folder. Missing files, links, paths outside that folder and
paths through `.state`, `.woobe-config` or `.git` fail before author files or the
registry change. Register existing artifacts when their files are already under
the configured root.

```sh
woobe resources create skill procedure --file ./author/skill.yaml
woobe resources clone skill '@procedure' --alias procedure-copy
woobe resources move skill '@procedure' --path procedures/skill.yaml
```

Registered descriptors can be folders or individual YAML/JSON files. Pull keeps
their paths and places declared support files beside the descriptor, including
after a move. Paths must work on all supported platforms: Windows device names,
trailing dots/spaces, alternate data streams and private metadata directories
are rejected on every OS. Automatically generated aliases avoid device names.

### Reconcile pending writes

If a managed write times out or loses its response, keep its private checkpoint
and run `woobe agent '@support' reconcile` (or the corresponding Network command).
Reconciliation observes the original operation; it does not upload or apply a
second write and still works if local YAML was edited or became invalid.
For a running operation, the returned `next_command` is
`woobe package status OPERATION_ID`; add `--wait` to observe until terminal.
Run the managed `reconcile` again afterward to accept completed local bases and
clear the pending state before another push.

### Diagnose a development connection

`context use` selects the global default. A project's `.woobe-config` can pin a
different connection; an explicit `--context NAME` takes precedence.

```sh
woobe package doctor --output json
woobe package doctor --context local --output json
woobe agent AGENT_UUID pull --alias support --context local
```

The read-only diagnostic reports the effective API/context, expected and server
catalog digests, authority-fingerprint validity and managed-development support.
An incompatible result exits with code 10 and retains the evidence. It does not
create private state or display credentials or authority fingerprints.

`catalog_status: windows_crlf` identifies a server hashing a Windows CRLF checkout
without normalization. Update Woobe's backend with the LF-normalized digest fix
and restart the API. Reinstalling the CLI or rerunning `init` cannot change that
server hash. Genuine catalog mismatches still require matching backend/CLI schemas.

`PACKAGE_EXPORT_INCOMPLETE` reports whether a ModelSpec, Provider credential
binding, matching Provider, or Project Environment field is missing. These are
classified from exact fixed owner reasons; arbitrary server messages and protected
input values remain excluded. Draft pulls require the backend fix that captures
the live Agent definition even when a saved legacy Draft has no ModelSpec.
Historical environment and explicit snapshot exports remain exact.

In PowerShell, quote comma-separated field lists:

```powershell
woobe agent get AGENT_UUID --fields "id,name,provider,model,provider_credential_id" --output compact
```

Isolated ASaC Drafts use explicit `draft open/select/show/push/checkpoint/reconcile`
operations. They preserve the native singleton Draft and Production while storing
a verified closed artifact. See [ASaC](ASAC.md#isolated-remote-drafts) for generation
preconditions, checkpoint integrity, capability negotiation and uncertain writes.

Local sealed revisions can restore author files with
`woobe agent '@support' checkout --revision REVISION_ID` (Network has the same
command). This requires a clean source checkpoint, preserves origin/bindings and
protects shared dependencies. See [ASaC source restoration](ASAC.md#restore-local-author-source)
for the source retention and server verification boundaries.

For diverged sealed branches, `woobe agent '@support' rebase --onto REVISION_ID`
performs a guarded local three-way merge. Concurrent field or support-file changes
are reported for explicit resolution. `revision merge REV_A REV_B --message 'Resolved content'`
then records already resolved files with both parents. Networks use the same flow;
see [reconciliation details](ASAC.md#reconcile-sealed-local-branches).

After a clone without private `.state`, select an existing isolated Draft with
`woobe agent '@support' draft select NAME_OR_UUID` (or `woobe network`). This uses
matching durable origin and authorized remote identity; it does not create a
Draft, restore files, recover Provider secrets or enable ordinary native push.
A pending write must be reconciled before changing selection. Known same-origin
roots refuse `create` when their private binding is missing; use explicit clone
with a new UID only when another resource is intended.

A fresh `pull` of an Agent or Network with existing ASaC history reuses the
logical UID captured by its authorized owner. Changing the local alias does not
change that identity. A conflicting existing local UID is rejected before any
author files are written; recover the original history rather than rewriting
its UID. Frozen Network constituents retain distinct local snapshot artifacts.

Provider connection defaults and Model overrides remain distinct during compilation.
A Provider's `base_url` stays in its public credential requirement metadata; it
is not injected into, or allowed to replace, the Model's explicit `base_url`.
An absent Model override remains absent. This preserves frozen Network component
definitions during an unchanged pull/push round trip while the native credential
retains its authorized connection settings.

New author objects record `compiler_recipe: woobe-development-compiler@2.0`.
Source objects without this field retain the earlier lowering recipe for exact
checkout verification. Their immutable hashes and executable objects are not
rewritten. New checkpoints/rebases use the current recipe; recompilation can
therefore produce a different definition from the historical one.


### Accepted native generations

After a successful native `push` or `reconcile`, the CLI checks every approved
resource against the original operation, definition and native identity before
updating local bases. When the server advertises accepted binding generations,
it uses the generation recorded in the native transaction, even if a later edit
has changed the current generation. Incomplete, missing or superseded evidence
leaves the checkpoint pending; preserve it and investigate with `reconcile`.
Do not delete private state to bypass this check or resend the accepted write.

### Isolated lifecycle preparation

Stage an exact registered checkpoint using `stage --revision REVISION_ID --yes`.
The selected remote Draft and retained executable object are the source; current
YAML changes are excluded. Inspect with `candidate CANDIDATE_UUID`. This freezes
Agent/Network snapshots independently of native environment selections and does
not publish or activate. `stage` without `--revision` retains legacy promotion.
See [ASaC Candidate preparation](ASAC.md#prepare-an-exact-immutable-candidate) for
the complete checkpoint and uncertain-response flow.

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

## Publish an exact evaluated Agent Candidate

```sh
woobe agent '@support' publish --candidate CANDIDATE_UUID --evaluation EVALUATION_UUID --notes 'Validated support update' --yes
woobe agent AGENT_UUID publication PUBLICATION_UUID
woobe agent '@support' history verify
```

This explicit flow requires CLI 0.26+ and a backend advertising Agent in
`asac.candidate_publication_kinds`. It requires a ready Candidate and a passed
Evaluation for the same retained revision, runtime and bindings. The server
rechecks those bindings and publishes the frozen Candidate, even if current
Staging subsequently changed. It never pushes local YAML or activates Production.
Native Release reuse still produces a separate publication provenance receipt.

Acceptance requires the registered development resource and its private state;
inspection by native UUID does not require `.woobe-config`. The CLI persists the
original operation before POST and mirrors its immutable receipt after acceptance.
An unknown remote outcome blocks another write. A local documentary failure after
remote commit exits with code 10 and retains the pending operation. In both cases,
use `woobe agent '@support' draft reconcile`: it reads the original operation and
retries the local mirror, without another publication request.

`history verify` checks receipt integrity and destination identity. Its
`publication_authenticity: integrity_checked_connection_unverified` distinguishes
an authenticated fetch observation from a signed offline attestation. Git claims
remain declared; this flow does not claim verified pipeline provenance.
Legacy publication without `--candidate` retains its native behavior; in
particular, legacy Network publication activates Production. Exact Network publication uses the explicit Candidate flow below.


## Publish and recover an exact Network Candidate

```sh
woobe network '@support-network' publish --candidate CANDIDATE_UUID --evaluation EVALUATION_UUID --notes 'Validated Network update' --yes
woobe network NETWORK_UUID publication PUBLICATION_UUID
woobe network NETWORK_UUID publication PUBLICATION_UUID reconcile --yes
woobe network NETWORK_UUID publication PUBLICATION_UUID cancel --notes 'Discard unfinished preparation' --yes
woobe network '@support-network' draft reconcile
woobe network '@support-network' history verify
```

Use CLI 0.27+ with a backend advertising Network Candidate publication. Prepare
and evaluate a new Candidate with `network-execution-runtime@2`; historical
Candidates retain their original runtime scope. Publication copies or reuses
immutable constituent Agent Releases through their owning module and creates the
Network Release from that exact tested composition. Production, current native
Draft/Staging and standalone Agent environment selections remain unchanged.

The server accepts the original publication before constituent copying. A failure
can leave `state: preparing` with prepared/required counts. The CLI exits 9 and
retains its pending operation, blocking a second publish. Inspect the returned
Publication UUID, then explicitly resume with `publication ... reconcile --yes`.
The server rechecks current permissions, original Evaluation and binding versions;
resume reuses original child-operation receipts rather than copying twice.

Alternatively, cancel an unfinished preparation with a reason. Cancellation seals
it without publishing the Network; already copied immutable Agent Releases remain
retained. Cancellation cannot undo a completed publication. These native UUID
recovery operations do not require `.woobe-config`.

After either terminal outcome, use `draft reconcile` for the original local
operation. It only reads original acceptance/current phase, mirrors the publication
or cancellation receipt, and clears pending state after the mirror succeeds.
It never repeats publication, constituent copying or activation. Documentary
failure exits 10 and remains recoverable; `history verify` checks both receipt
collections. Offline verification proves content integrity, not server authenticity.

Workflow reservations use `woobe agent '@support' lease acquire --scope draft`
(and Network equivalents). Renew/release present privately retained workflow
proofs; `lease reconcile` recovers original acceptance without another mutation.
See [ASaC workflow reservations](ASAC.md#bounded-workflow-reservations) for scope,
expiry, native UUID flags and administrative break.

Exact Release selections use `agent|network REFERENCE deployment plan` with an
explicit Release, expected environment generation and audit reason, followed by
a short environment lease and `deployment apply PLAN_UUID --yes`. Recover lost
responses with `deployment reconcile`; see [ASaC](ASAC.md#exact-release-deployment-plans).

Managed Project gates apply to development and legacy promotion at the server. Inspect policy with `woobe project lifecycle show`; local registry, author locks and `--yes` do not bypass it. Administrative changes are documented in [Project lifecycle policy](PROJECT_LIFECYCLE.md).

Binding recovery accepts the empty private pending marker left by a completed
ASaC operation. Unresolved or malformed checkpoints still block recovery;
reconcile the original operation before trying again.

## Display name and local alias

`uid` identifies a logical local resource, `alias` is a local reference, and
`metadata.name` is the presentation name compiled for create/push. Clone creates
a new UID and alias and preserves the presentation name; edit `metadata.name`
explicitly to rename the clone. Runtime Skills additionally require their cloned
manifest name to match their new identity. Changing an alias never renames a
remote Agent/Network. Push/create dry-run shows the intended `name`; inspect the
remote getter after the original operation completes. Names can duplicate; UUIDs
and registered aliases remain the unambiguous operation references.

## Unified delivery

See [Deployment](DEPLOYMENT.md) for exact Release/Staging/local delivery, private intent recovery and explicit rollback. See [CI deployment](CI_DEPLOYMENT.md) for deploy-only authority and encrypted checkpoints. Existing commands retain their semantics.
