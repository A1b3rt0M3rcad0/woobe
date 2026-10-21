# Deploy qualified Releases from CI

Use [deploy-release.yml](examples/deployment/deploy-release.yml) as a manual
workflow in your application's repository. It deploys an exact existing Release
using UUIDs and a clean runner, independently of author registry/provider secrets.
It runs on `[self-hosted, Linux, X64]`; dedicate the runner to trusted delivery.
Required tools are bash, curl, tar, sha256sum, Python 3, gh and gpg.

Create a GitHub `production` Environment with required reviewers and restricted
branches. Protect workflow changes. Configure these Environment values:

| Type | Name | Value |
| --- | --- | --- |
| Variable | `WOOBE_API_URL`, `WOOBE_WORKSPACE_ID`, `WOOBE_PROJECT_ID` | Exact destination |
| Variable | `WOOBE_CLI_VERSION`, `WOOBE_CLI_SHA256` | Reviewed release version and independently verified Linux amd64 archive checksum; no `latest` |
| Secret | `WOOBE_DEPLOY_KEY` | Dedicated Control Key with Project reads and target-scoped `agent:production` / `network:production` |
| Secret | `WOOBE_CHECKPOINT_KEY` | Strong separate recovery encryption passphrase, preserved across attempts |

Current owner qualification may require read access to the frozen dependency
closure (Models, Providers, Tools, Skills, Knowledge, Secrets and environments).
Use actual backend permission diagnostics and explicit target/environment
conditions. Do not grant authoring, publication, key management or policy writes
to deploy-only credentials. In Project lifecycle policy, enable `managed` and
add the credential's stable actor `control:CONTROL_KEY_ID` to `production_actors`.
An allowlist entry does not grant permissions; grants alone do not bypass policy.

The workflow pins Actions by commit, verifies the CLI archive SHA-256 before
execution and uses Environment authorization before deployment. Inputs enter
shell through environment variables. A target-scoped concurrency group complements
server CAS/leases rather than replacing them. Stable intent includes workflow
run ID (not attempt number), API, Workspace, Project, target and Release.

It encrypts the private journal with GPG integrity protection before storing the
recovery artifact. Re-run downloads/decrypts the original checkpoint and invokes
`resume`; if the artifact/checkpoint is absent or decryption fails, it stops.
No blind replay or replacement intent on retry. Review artifact access/retention
and protect the encryption key. Losing either requires an operator to reconcile
original server operations, then approve a new delivery explicitly.

Only a bounded public receipt summary is uploaded unencrypted. Keys, provider
bindings, raw journals, `.woobe/.state` and request inputs are excluded. Production
activation does not attest Git source: existing signed/Git custody gates remain
separate. Record run URL alongside the receipt for review.

## Optional build/publish then deploy

Use separate protected builder and deploy jobs with separate Environment secrets.
The builder must start from a privately restored accepted registry and source
custody; a source checkout alone does not recreate accepted bindings. Run:

```sh
woobe agent '@support' deploy --from local --env staging --suite tests/evaluation.yaml --notes 'Build and qualify pipeline revision' --intent BUILD_INTENT_UUID --checkpoint PRIVATE_BUILD_JOURNAL --yes --output json > build-receipt.json
```

This qualifies/publishes the exact Revision and selects it in Staging using the
builder's explicit `:write` and `:version` authority. It requires no Production
grant. Extract `data.release_id`, `data.publication_id` and target UUID from the
validated successful receipt; pass only those public IDs to the protected
Production job's release mode. Keep builder source/credentials/checkpoints private
and recover its original intent before another build. Production job uses the
example's native UUID flow and dedicated deploy key.

For a publish-only build, retain the existing `draft open/push`, `revision create`,
`draft checkpoint`, `stage --revision`, `test --candidate` and
`publish --candidate --evaluation` sequence. Do not claim an unqualified fresh
checkout can publish. Choose the build's source/policy gates explicitly; this
optional composition is not an OIDC or cross-instance transport feature.

## Evidence boundaries

Paired CLI/backend acceptance drives real PostgreSQL owners, outbox, deterministic
provider workers, both resource kinds, clean UUID delivery, rollback and truncated
committed HTTP responses. It is not a customer Production deployment, a multi-host
load benchmark or external-provider certification. GitHub Environment review and
secret configuration are operator-owned; examples do not configure your account.
