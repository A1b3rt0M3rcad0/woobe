# Trusted pipeline Git provenance

Publication Git metadata remains `declared` until a separately authorized pipeline
attestation is accepted. The original Publication and revision are immutable.
An instance receipt signature authenticates the owner record, including its
original `declared`/`unavailable` status; it does not prove repository origin.

## Explicit operator trust

`WOOBE_ASAC_GIT_TRUSTED_BUILDERS` is an optional JSON array (empty by default).
Each entry has exactly `issuer`, `instance_id`, `principal`, `project_ids`,
`repository`, `public_key`, and `status` (`active` or `revoked`). The principal is
`control:CONTROL_KEY_UUID`; Projects are an explicit nonempty UUID list. Repository
is `owner/repository` or a public credential-free HTTPS URL, matching the pipeline
proof exactly. Public keys are canonical unpadded base64url Ed25519 keys.

The pipeline keeps a **separate private seed** in a private regular CI secret file.
It is not a CLI Key or the instance receipt-signing/root key. Never place the seed,
provider secrets or private registry `.state` in Git or API configuration. The API
only receives builder public keys and exact authorized scope. No key or claimed
commit is trusted by default. Configuration changes require a controlled API
restart; revocation blocks new attestations, without rewriting accepted history.

## Non-circular workflow

1. Seal, retain, Stage, evaluate and publish exact source/definition content.
2. Commit the author YAML/support files, config and public history/objects. The
   immutable revision does not contain a future commit SHA.
3. A clean trusted checkout verifies regular committed Git blobs against the exact
   retained author closure and recorded canonical compiler, then signs a separate
   proof for the original Publication. Use CLI 0.32+ `git-proof`; output goes into a
   new exclusive YAML/JSON file after the commit.
4. `git-attest` submits that signed proof with an explicit original operation UUID.
   Owner authority, issuer/principal/instance/repository/Project scope, Ed25519
   signature, typed payload digest and database-clock expiry are rechecked.
   Maximum validity is one hour. The retained compiler-verified author artifact
   and exact revision/record/definition digests must match that Publication.

Agent/Network endpoints are `/projects/{project_id}/{agents|networks}/{resource_id}/asac/git-attestations`;
POST accepts a signed proof and operation identity, GET `/{operation_uuid}` reads
the original append-only receipt. This changes neither publication nor Production.
A rejected request leaves no accepted Git receipt. An authorized original replay
returns the original receipt without reinterpreting historical expiry/trust.

Server status `verified` is scoped to `trusted_pipeline_at_acceptance`. Local
`pipeline_signed_not_server_verified` is not a server endorsement. The trusted
builder is responsible for checkout hosting identity; local Git URLs are not
independent authority. A timeout/failed Git step after deployment never repeats
activation: inspect the original operation and keep documentary evidence separate.
These independent receipts do not change offline instance-signed exports.

Tests share deterministic **test-only** Ed25519 fixtures with Go, exercise exact
Git bytes/compiler integrity, wrong scopes/revocation/expiry, owner custody/content
binding and immutable original replay. Signing seeds used in fixtures are never
operator credentials.
