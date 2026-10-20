# ASaC origin and history

These commands need a CLI build with ASaC history support. Check targeted help
first; do not infer availability from the presence of a runtime Release command.
Remote reads also need the server's ASaC read contract. A legacy server can reject
them; do not silently downgrade that observation to a verified current selection.

Keep lockfiles, revisions and referenced objects with author files. Keep `.state`
private. Lockfile origin is historical; observing a changed Production must not
rewrite it. A revision is a local checkpoint, not publication or approval.

```sh
woobe agent '@support' revision create --message 'Correct citation instructions'
woobe agent '@support' history
woobe agent '@support' history verify
woobe agent '@support' status --remote
woobe agent AGENT_UUID current --env production
woobe agent '@support' history fetch
```

Networks use the same vocabulary. Local history works without remote access.
`history fetch` adds immutable receipts without replacing YAML or Production;
it verifies traversal through a stable scoped watermark. History metadata,
object availability and runtime executability are different facts.

Compare `local_modified`, `draft_changed` and `tracked_ref_changed` separately.
Offline status is `unverified`. `legacy_unavailable` environment generation is
not a CAS token. Hashes prove integrity, not server signatures or verified Git
provenance. Missing objects or unknown origin require explicit recovery; never
invent parents, commits, bindings or activation authority.

History support does not change legacy publication effects. Agent publish creates
a Release; Network publish also activates Production. Checkpoint creation alone does
not open an isolated Draft or provide fenced deployment guarantees.

For isolated remote Draft storage, check server capability and targeted help:

```sh
woobe agent '@support' draft list
woobe agent '@support' draft open hotfix --from production
woobe agent '@support' draft show
woobe agent '@support' draft push
woobe agent '@support' draft checkpoint REVISION_ID
woobe agent '@support' draft reconcile
```

The same flow applies to Networks. Opening preserves author files; it is not a
local checkout. `draft push` saves a closed artifact with the observed generation,
without changing default native Draft, Staging or Production. A checkpoint must
match the exact saved artifact and unchanged YAML. An unsupported server is
refused; never fall back to default Draft writes. Private operation identity is
saved before writing. Reconcile only reads the original operation; missing receipt
or unknown outcome never licenses a second write. Semantic qualification remains
`stage_required` until the negotiated candidate lifecycle is available.

For local author restoration, use `woobe agent '@support' checkout --revision REVISION_ID`
or the same Network command. Checkpoint current edits first. Checkout rejects local
or shared-file changes; do not delete files or private state to bypass that check.
Keep `objects/author` with local revision history for offline clones. The optional
remote author digest is declared metadata, not a server-verified source attestation;
closed executable package verification remains separate.

`woobe agent '@support' rebase --onto REVISION_ID` reconciles sealed local branches
against their common ancestor. Checkpoint local edits first. Arrays and support
bytes are atomic; conflict diagnostics give paths without changing author files.
Use an explicit known `--base` only when ancestry has multiple possible bases.
After resolving content yourself, `woobe agent '@support' revision merge REV_A REV_B --message 'Resolved content'`
seals the current files with both parents; it does not automatically merge them.
Networks have the same commands. Neither operation is a push or deployment.

For server-signed export and offline verification with a separately pinned root,
read [signatures](signatures.md). Unsigned history integrity checks do not
establish offline server authority.
