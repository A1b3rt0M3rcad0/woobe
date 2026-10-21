# Local YAML development

After cloning without private bindings, run `woobe agent '@support' bindings recover`
(or Network), optionally previewing with `--dry-run`. This verifies the entire
accepted native closure without editing YAML or recovering an accepted author
base. Bind Providers explicitly afterward; stale generations stay stale.

Use `.woobe-config` only for managed development. If it exists, check it; do not
delete it or `.state/`. Repeating `init` preserves the registry and can add/update
assistant setup; see [setup](setup.md). Initialize a new project explicitly:

```sh
woobe init --agents codex --root .woobe --context local
woobe agent AGENT_UUID pull --alias support
woobe network NETWORK_UUID pull --alias service
```

Pull registers the root and its dependency closure, reusing bound shared native
identities. The default is current Draft. `--env staging` and `--env production`
select their current frozen definitions; `--env release --version VERSION`
selects one exact Release. Unavailable environments fail without fallback.

With a compatible server, managed pull uses Package 2.0: Provider authentication
stays a typed remote key reference. Local validation/push/checkpoint/Stage preserve
it; no local environment or credential-store lookup supplies its value. Draft
push is structural, and a prepared Candidate does not prove runtime readiness.
Keep old schema1 history unchanged; an incompatible advertisement must be fixed,
not bypassed by silently downgrading the package.

Artifact access is an opt-in Package 2.0 logical Agent/Network policy. Bind a
required, non-model-exposed External Context string at `run` or `session` scope,
then declare the Workspace namespace, actions, limits and optional pinned
processing profile. Package validation checks structure; the Runtime service
resolves and authorizes the destination Workspace. No OpenAI API key is needed.
See [portable package policy](packages.md).

Edit the registered `agent.yaml`/`network.yaml` and declared support files. YAML
uses blocks and multiline text; JSON descriptors remain accepted. Stable registry
keys are used in refs inside YAML; `@alias` is for terminal commands.

```sh
woobe agent '@support' validate
woobe agent '@support' diff --output compact
woobe agent '@support' push --dry-run
woobe agent '@support' push
```

Local validation cannot certify server semantics or authorization. Managed push
dry-run uploads/plans against the server without applying Draft changes. A normal
push updates the existing Draft only, with identity/revision evidence and a
semantic merge. Conflicts stop the write. Staging/Production require separate
lifecycle commands. Repeat the same workflow for `network`.

Create a new root explicitly with a local author descriptor referencing existing
registered dependency keys:

```sh
woobe resources create agent support-new --file ./agent-author.yaml
woobe agent '@support-new' validate
woobe agent '@support-new' create --dry-run
woobe agent '@support-new' create --yes
```

The bundled [author template](../assets/agent-author.yaml) requires replacing the
Model ref with a real registry key. It is not an apply-ready example. Clone uses a
new UID; `woobe resources clone agent '@support' --alias support-copy` intentionally
creates another local identity while sharing appropriate dependencies. Do not
use clone/create for an update. `resources move` and `resources alias` preserve UID.

An Agent/Network pull into a fresh registry preserves its owner's existing ASaC
UID. A mismatching established local UID stops the capture before writing files;
recover original history instead of rewriting identity or creating a duplicate.
Frozen Network constituent snapshots remain distinct local artifacts.

Use `--path` only for a path within the configured registry root. Inspect
`resources list` rather than guessing file names or adding duplicate entries.

For isolated remote authoring, select an existing line without duplication:

```sh
woobe agent '@support' draft list
woobe agent '@support' draft select hotfix
woobe agent '@support' draft show
```

Networks support the same commands. Matching durable origin allows selection
without private state. This does not change YAML, create a line, restore native
push bindings or copy credentials. Reconcile uncertain writes before selection.
Local `rebase --onto REVISION_ID` preserves incoming comment-only edits and stops
on competing comments, semantic fields or support files. Seal manual resolutions
with `revision merge REV_A REV_B --message 'Resolved content'`.


### Fetch isolated revision metadata

Use `woobe agent @support history fetch --revisions` (or the same Network
command) to append the authorized server revision catalog. It checks immutable
record digests, logical identity, page completeness and a stable watermark.
The default `history fetch` continues to retrieve native release/deployment
receipts. Neither mode changes author YAML, the working head or Production.

Revision metadata and source materialization are separate: this fetch reports
`objects_available: not_downloaded`. A remote source digest is a declaration,
not a retained author object or a server attestation. Local checkout still
requires verified executable and exact author objects. `--dry-run` validates
the catalog without storing metadata. A failed traversal can retain earlier
immutable pages, but never reports that traversal as complete.

```sh
woobe agent @support history fetch --revisions
```


### Hydrate a retained executable object

```sh
woobe agent @support history fetch --revisions
woobe agent @support revision hydrate rv_00000000-0000-0000-0000-000000000000
```

Replace the revision placeholder with a verified retained ID. Agent and Network
use the same operation. It negotiates backend hydration support, reauthorizes
the retained resource and verifies the receipt, transport SHA-256, inventory,
artifact digest and executable definition before storing an immutable object.
`--dry-run` downloads and verifies without storing. Source YAML, native bindings,
working head and Production are preserved. Author objects are reported separately:
when retained by the backend, exact author source is also downloaded and recompiled against the sealed definition before local storage. A separate guarded checkout restores YAML/comments/support files. Legacy records without retained source report it unavailable. Credentials and native bindings are not restored, and hydration does not qualify execution.

Guarded checkout verifies both the current clean source anchor and the target revision. If author objects were removed or absent in a clone, hydrate both revision IDs first. This recovery never bypasses protection of local edits.

Names and aliases are separate: clone creates a new UID/alias but keeps an
Agent/Network's `metadata.name`. Edit that field explicitly before create/push to
rename the presentation. Runtime Skill clones also rename their manifest identity.
Dry-run create/push shows the compiled `name`; aliases never rename remote roots.
