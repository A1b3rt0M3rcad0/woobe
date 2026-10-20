# Portable transfer

Use package export/import for portable composition. Root `export` and
`agent export` are partial JSON projections, not apply-ready packages.

```sh
woobe package export agent AGENT_UUID
woobe package export network NETWORK_UUID --env production
woobe package export agent AGENT_UUID --env release --version VERSION
woobe package validate ./exported-agent --locked
woobe package bindings ./exported-agent --destination ./destination.yaml
woobe package plan ./exported-agent --bindings ./destination.yaml --save-plan ./plan.json
woobe package import --plan-file ./plan.json --wait
```

Export also accepts an exact name. It defaults to current Draft and creates
`./normalized-resource-name`; existing destinations are not replaced. Do not
require snapshot UUIDs. `--version` selects a Release with `--env release`;
`--package-version` overrides portable metadata only.

Inspect declared requirements and fill the generated binding template with
destination native identities/private references. Omit `--bindings` when there
are no requirements. Keep bindings/plans outside the portable directory and
never put raw credentials in them. SOURCE also accepts `woobe.yaml` or tar.gz.

By default a present lock is verified, even without `--locked`; that flag
additionally requires a lock. For an already edited copy, use
`woobe package validate ./edited --structure-only`: it checks current schemas,
references and path/size limits, reports `capture_integrity: not_evaluated`, and
never certifies the old capture. It cannot be combined with `--locked` or used
to bypass integrity in planning/import. Neither mode rewrites a lock. Do not edit the captured copy or remove its lock to hide drift.
Create a separate editable author, edit it, then produce a new sealed copy:

```sh
woobe package edit ./captured --destination ./author
woobe package validate ./author
woobe package seal ./author --destination ./sealed
woobe package validate ./sealed --locked
```

`edit` verifies the sealed source before copying and omits the old lock only in
the new author directory. `seal` validates the current author and writes a new
inventory lock in another directory. Neither overwrites a destination or mutates
the source; server semantics and destination permissions still require a plan.

Import creates Draft resources even when exported from Production; it is not the
managed update flow. Editing an existing resource uses pull/push. Repeating an
import reconciles its checkpoint, not an intentional second create. Keep the
checkpoint and use `woobe package status --checkpoint PATH --wait` after uncertainty.


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

HTTP group routes can declare their own remote `authentication` in schema 2.0.
Declare each referenced key in the manifest. Omitted route authentication inherits
the connection; explicit `none` suppresses private parent headers. A protected
typed route requires 2.0 export; never replace its reference with a local token.

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

For schema2, `package bindings` keeps schema2 and proposes explicit creation;
review create/reuse choices before planning with `--structural`. Remote keys have
no local `protected_ref` material. Managed pull/checkpoint uses the separately
advertised ASaC v2 definition scope and preserves immutable v1 history.
