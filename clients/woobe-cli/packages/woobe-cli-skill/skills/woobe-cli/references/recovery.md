# Recovery without data loss

| Failure | Next step |
| --- | --- |
| Missing private native bindings after clone | `woobe agent '@support' bindings recover --dry-run`, then recover after review (or Network). Entire closure must have accepted server evidence; explicitly bind Providers afterward. Does not recover an accepted YAML base |
| Missing isolated Draft selection after clone | `woobe agent '@support' draft select NAME_OR_UUID` (or Network); matching origin required; no remote mutation or file checkout |
| Rebase comment conflict | Resolve the reported author comments explicitly; checkpoint the resolved content rather than dropping either edit |
| Missing registered descriptor | `woobe config check`, then inspect the named path; restore accidental deletions or preview `woobe resources prune --dry-run` |
| Several intentionally deleted folders | Review the preview, then `woobe resources prune --yes`; only absent descriptors are unregistered |
| Missing Model still used by an Agent | Restore the Model or edit/remove that consumer's reference; pruning must not create a broken graph |
| Unavailable/unsafe local file | Inspect permissions, links and the reported path; do not disable safety checks |
| Package schema/fingerprint mismatch | `woobe package doctor --output compact`; align server/client, restart updated backend when applicable |
| `PACKAGE_EXPORT_INCOMPLETE` | Inspect the narrowed Model/Provider/environment diagnostic; fix the actual source definition rather than installing repeatedly |
| Pull merge conflict | Resolve only listed local/remote fields; preserve author files and the accepted base |
| Push response lost or timed out | Keep `.state/`; `woobe agent '@support' reconcile` or Network equivalent before another write |
| Import uncertain | Keep its checkpoint; `woobe package status --checkpoint PATH --wait`, then reconcile the original operation |
| Pending reconciliation points to status | Observe the given operation until terminal, then rerun managed reconcile to accept bases |
| Publication or permission denied | Stop and report the actual scope/required permission; `--yes` grants no authority |
| Artifact upload start/part/finalize is uncertain | Keep the private checkpoint and run `woobe artifacts upload resume --checkpoint PATH`; resume verifies the same source and reconciles the original operation/offset |
| Artifact upload source digest changed | Restore the exact original bytes at the checkpointed path or inspect/abandon the staged upload deliberately; never resume different content |
| Artifact revision compare-and-swap conflict | Read the Artifact and its exact current revision, review the change, then start a new intentional replacement with the new expected revision |
| Artifact download is incomplete or fails SHA-256 | No final file was published; retain the destination and retry the same immutable revision after resolving the transfer failure |

`resources unregister KIND '@alias'` removes one local registry entry, including
an absent root descriptor, after validating remaining refs. It retains files and
private native bindings and does not archive/delete server resources. Prune does
not delete unused but present dependencies or accept malformed/linked files as
missing. Do not delete `.woobe-config` or `.state/` as a generic repair.

Use only read-only diagnosis before choosing a repair. Do not copy full private
config/state, CLI Keys, provider secrets or sensitive runtime output into reports.
Confirm operation identity/revision/evidence instead of guessing from names.

Selecting a Draft recovers only private Draft observation. It does not recover
ordinary native push bindings or Provider credentials. Reconcile an unresolved
original write before switching selection. Do not use `create` as a binding repair
for a known same-origin root: clone with a new UID only for intentional duplication.


### Accepted native generations

After a successful native `push` or `reconcile`, the CLI checks every approved
resource against the original operation, definition and native identity before
updating local bases. When the server advertises accepted binding generations,
it uses the generation recorded in the native transaction, even if a later edit
has changed the current generation. Incomplete, missing or superseded evidence
leaves the checkpoint pending; preserve it and investigate with `reconcile`.
Do not delete private state to bypass this check or resend the accepted write.

For an uncertain `test --candidate`, use `draft reconcile` to recover the original Evaluation UUID. Then inspect `evaluation UUID` or `evaluation UUID reconcile --yes`. These commands never execute another case; do not retry the test to infer its outcome.

For exact Candidate publication, retain the original pending operation. An unknown acceptance or exit 10 after local receipt failure requires `woobe agent '@support' draft reconcile`; never repeat publish to repair its local mirror.

Network Candidate publication can remain accepted with partial immutable constituent copies. Do not repeat publish. Inspect `woobe network NETWORK_UUID publication PUBLICATION_UUID`, explicitly resume with `reconcile --yes` or cancel with `cancel --notes REASON --yes`, then run the original local `draft reconcile` to mirror terminal evidence. Cancellation preserves unused immutable child Releases and cannot undo published Networks. See [lifecycle](lifecycle.md).

Lease acceptance uses private pending operations. Read the original with `lease
reconcile` or `draft reconcile`; never repeat acquire after an uncertain response.
Expired/superseded proofs are intentionally retained and fenced by the server.
Explicit release or a deliberate new acquisition is required to change workflow
ownership; `lease show` never adopts a reservation.

For an unresolved exact Release selection, use `woobe agent '@support' deployment
reconcile` (or Network). It reads the recorded original operation and mirrors the
receipt before clearing pending state. Do not repeat apply. Native UUID recovery
requires the original `--operation UUID`; no project configuration is needed.


Managed lifecycle rejection on legacy Agent/Network promotion requires the
ASaC Candidate/evaluation/publication/deployment path. Do not change policy or
repeat legacy writes automatically. A confirmed stale policy generation needs
a fresh `woobe project lifecycle show` and an intentional new policy operation;
an uncertain policy write needs `woobe project lifecycle operation OPERATION_UUID`.

A completed ASaC operation seals its private pending checkpoint as an empty
object (`{}`). This is a cleared marker and does not block `bindings recover`.
A pending operation, partial record or malformed/unreadable checkpoint still
blocks recovery. Reconcile the original operation; do not delete an uncertain
checkpoint or manufacture a new operation ID to bypass it.

For server-signed export and offline verification with a separately pinned root,
read [signatures](signatures.md). Unsigned history integrity checks do not
establish offline server authority.

For `git-attest` uncertainty, inspect `woobe project agent git-attestation get RESOURCE_UUID ORIGINAL_OPERATION_UUID` (Network equivalent). Correct trust/source issues before another operation; never repeat deployment to repair Git evidence.

A missing Draft pending file or the exact cleared object `{}` means no pending
operation: `draft reconcile` succeeds with `pending=false` and no backend request.
An explicit `--operation` still requires a recorded matching write. Partial,
malformed, duplicate-key, wrong-target or trailing-data checkpoints remain errors;
never erase them to manufacture a clean state.

Network export/pull conflicts expose a `PACKAGE_EXPORT_NETWORK_*` diagnostic
and a bounded `/spec/nodes/...` or `/spec` path. Preserve the request ID. A
missing/invalid pinned constituent or corrupt snapshot cannot be repaired by
silently selecting the latest Agent or editing the captured hash.


For `ASAC_CANDIDATE_BINDING_UNAVAILABLE`, inspect the reported descriptor's
`metadata.key`. `network '@alias' bindings recover --dry-run` checks accepted
closure; a canonical create/pull alone need not establish it. Bind Providers and
use managed push, then refresh/checkpoint the isolated Draft and stage the exact
revision. Reconcile uncertain operations before another write.

For `PACKAGE_EXPORT_NETWORK_CONSTITUENT`, inspect the reported node's selected
Agent snapshot. A `/spec/model/primary` or `/fallback` suffix means missing
ModelSpec evidence. Recover mutable Draft configuration explicitly, or create a
new complete Draft/Candidate/Release for incomplete immutable history. Never
replace a pinned snapshot with latest or rewrite historical hashes.

For unified delivery and original intent recovery, read [deployment](deployment.md). Native UUID deploy works without the development registry; local delivery requires accepted source and bindings.

## Local delivery and completed Runtime observation

See [deployment](deployment.md) for source/ancestry preflight and recovery. Keep
original intent receipts: an interrupted local checkpoint is reused only with its
original intent and unchanged artifact. Do not create new intents repeatedly to
work around unaccepted ancestry.

`runtime target observe` needs a Runtime Key with the `stream` interface. An
HTTP-only key can run synchronously but does not grant observation. On a backend
with terminal reconciliation, observing a completed Run returns the durable final
state and closes even if Redis still says running; it does not execute again.
A legacy Network with incomplete pinned constituent snapshots needs operator
review of the reported node/dependency. Updating the CLI or substituting today's
Agent Draft does not repair the immutable original. Missing instance signing
configuration also requires operator setup, not a generated replacement trust key.

## Native test and issuance recovery

`release run-test` and saved-snapshot `agent UUID test` default to two minutes;
explicit `--timeout` wins. Before POST the CLI stores a private test UUID/hash.
On timeout preserve `test_id` and execute its exact `recovery_command` to list
results for the selected snapshot. Pending/absent observation is not a failure
proof. Never repeat POST to discover the outcome; do not remove the intent.

`PACKAGE_REVISION_CONFLICT` reports the dependency, expected/observed generation
and binding path. Doctor does not refresh the base. Pull its owning Agent/Network,
review the diff and plan again; do not create a duplicate Model or bypass CAS.

Issued-secret files are private JSON envelopes (`woobe-issued-secret`, file schema
`1`), with the native `data.key` retained. Failed requests leave no final stub.
Credential import / CLI-Key stdin login validate the documented or legacy envelope
and accept a raw token. Never use full JSON as an HTTP bearer token or print it.
A committed issuance with a local file failure requires inspection/rotation,
not an automatic second issuance.

Configuration-aware API failures retain `CONFIG_*` codes and the affected key and
Environment. For `CONFIG_VALUE_MISSING`, ask the authorized operator to fill the
value in Woobe; do not request the secret in chat or read a local environment
variable as a substitute. For `CONFIG_REVISION_CONFLICT` during deployment,
refresh readiness and create an explicit new deployment plan after review; keep
the immutable Release. For `CONFIG_STORE_UNAVAILABLE` or expired pinned versions,
reconcile any original operation before starting a new one. Candidate artifact
preparation can succeed with configuration pending; it does not prove execution
or Production readiness.
