# Shared dependencies

The registry distinguishes Agents, Networks, Providers, Models, Tools, Skills,
Knowledge, Prompts, Contracts and Surfaces, plus frozen constituent snapshots.
`.state/` holds private bindings and recovery evidence. Do not include it in
Git, portable exports or skill bundles.

Models require a Provider. Provider files describe public connection intent;
the native credential UUID is a private Project-scoped binding. A pull captures
it automatically. For an explicitly new local Provider:

```sh
woobe resources create provider primary --file ./provider.yaml
woobe project provider-credential list --output compact
woobe resources bind provider '@primary' CREDENTIAL_UUID
woobe resources create model chat --file ./model.yaml
```

Use an actual supported provider/model, its server schemas and project catalog;
do not invent model identifiers or include API secrets/base-URL credentials.
Model YAML uses `spec.provider_ref` with the stable local Provider key.

Inspect impact before changes with `woobe resources used-by model '@chat'` and
`woobe model usage '@chat'` / `woobe provider usage '@primary'`. Shared Model/Tool
edits can affect multiple roots. Keep one registered identity for a shared native
resource. Prompt/Contract/Skill and owned Tool clone semantics differ from shared
dependencies; inspect the actual closure rather than copying directory trees.

Skill/Knowledge support files must be declared; `resources create`, clone, move,
pull and package compilation carry only declared bytes. Missing or linked support
files fail validation. Runtime Skills uploaded to Woobe are different from this
terminal assistant skill.

Frozen Network constituent Agents cannot be pushed standalone. Pull their own
Draft or clone explicitly. Surface authoring references a registered Agent or
Network through `spec.target_ref`; pull/create its target first. Surface pushes
preserve its selected Release but may affect active surface configuration. Use
explicit lifecycle commands for activation/refresh and the user's intended scope.

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
