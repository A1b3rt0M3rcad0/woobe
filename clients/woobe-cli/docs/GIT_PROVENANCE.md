# Trusted Git pipeline provenance

This workflow requires CLI 0.32+ and the compatible backend. Git metadata supplied
at publication is a `declared` claim. An instance receipt signature authenticates
that owner record; it does not verify the claim's Git origin.

A separate trusted pipeline can attest an **existing** Publication. The instance
operator explicitly configures the issuer, public Ed25519 builder key, repository,
instance UUID, allowed Project UUIDs and the pipeline's Control Key principal.
The pipeline seed is separate from CLI Keys and from instance receipt signing.
No builder is trusted by default. The API receives only its public key.

## Source commit first, independent proof afterwards

1. Seal a local revision, retain/upload its compiler-verified author closure,
   Stage/test/publish it and keep the original revision and Publication identities.
2. Commit the exact author YAML/support files and `.woobe-config`. History and
   public content-addressed objects can be committed for clean-clone verification;
   private `.state`, credentials and signing seeds must be excluded.
3. In a clean trusted CI checkout, verify the exact commit's regular Git blobs
   against the retained author closure and canonical compiler. Do not use `HEAD`
   as the proof identity. Generate the proof into a separate exclusive file after
   the commit; never inject its future SHA into the source revision.
4. Submit that signed proof once with a fresh, saved operation UUID. The backend
   checks current authority, exact issuer/key/repository/Project/instance scope,
   database-clock expiry, sealed revision digests and retained source custody.

```sh
woobe agent '@support' git-proof --revision REVISION_ID --commit COMMIT_SHA --repository owner/repository --publication PUBLICATION_UUID --resource-id AGENT_UUID --issuer pipeline --instance INSTANCE_UUID --workflow-run RUN_ID --project PROJECT_UUID --signing-key-file /private/ci-builder.seed --path git-proof.yaml
woobe agent AGENT_UUID git-attest --file git-proof.yaml --idempotency-key OPERATION_UUID
woobe project agent git-attestation get AGENT_UUID OPERATION_UUID
```

All uppercase values are placeholders. Replace them with original retained
identities. Network uses the equivalent `woobe network` and
`woobe project network git-attestation get` commands. The `git-proof` reference is
local alias/UID/path; `--resource-id` is the independently confirmed native UUID.
Signing runs offline and requires development config/public history, not a copied
private registry state. The signing file must hold a private, regular base64url
encoded 32-byte Ed25519 seed (private parent/DACL on Windows); inject it through
CI secret files rather than command arguments. Remove the private file afterwards.

## Outcome and recovery

The local proof reports `pipeline_signed_not_server_verified`. The backend's
separate append-only receipt reports `verified` with
`verification_scope: trusted_pipeline_at_acceptance` only after authorization and
cryptographic/content checks. Publication, revision and Production are unchanged.
A proof is valid for at most one hour. An original committed replay preserves its
receipt even after expiry, while a new operation rechecks current trust and grants.

After timeout or an incompatible response, query the **original** operation UUID.
A 404 alone does not authorize retrying with a new identity. Correct permissions,
trust or source-custody problems first. Never treat an unsigned local document,
self-computed digest or arbitrary commit string as verified origin.

Git verification proves exact committed bytes and a configured builder's statement.
The operator's scoped builder is responsible for repository checkout identity; the
CLI does not infer hosting identity from an untrusted remote URL. Revoking a builder
prevents new attestations but does not rewrite the historical accepted receipt.
These receipts are separate from offline instance receipt-signature exports.

Git proof verification resolves the physical worktree and source paths before checking containment, including macOS temporary-directory aliases and Windows native path separators. Exact committed bytes remain required; configure `.gitattributes` explicitly when cross-platform line endings must stay unchanged.

Proof verification disables local Git replacement refs and checks object integrity. A mutable local substitution cannot make a different commit appear to contain the retained source.
