# Server signatures and explicitly pinned trust

Use CLI 0.31+ and a backend with instance receipt signing configured. Read-only
export uses the authorized lifecycle owner's exact record; no receipt body is
accepted from the client.

```sh
woobe agent UUID receipt publication PUBLICATION_UUID --path publication.yaml
woobe network UUID receipt deployment DEPLOYMENT_UUID --env production --path deployment.yaml
```

`revision` takes a revision ID; `evaluation`, `publication`, `deployment` take
receipt UUIDs. Existing files are not overwritten. YAML/JSON follows extension.
Native UUIDs do not require `.woobe-config`.

Pin only a fingerprint confirmed independently by the instance operator:

```sh
woobe trust pin publication.yaml --root-fingerprint ROOT_FINGERPRINT --path trust.yaml
woobe receipt verify publication.yaml --trust trust.yaml
woobe trust refresh fresh-publication.yaml --trust trust.yaml --path trust-next.yaml
```

The uppercase values are placeholders, including the operator-confirmed
`sha256:...` fingerprint. Verification is offline and checks exact payload,
root/key signatures, scope, validity, revocation and manifest expiry. Trust
refresh rejects lower epochs, same-epoch rewrites and changed instance/root.
It writes a separate public file for review; it does not replace trust silently.

Report the trust epoch/expiry. A signature does not claim current selection,
executable availability or permission, and does not turn declared Git metadata
into verified provenance. Offline trust cannot discover newer revocation until
refreshed. Keep private seeds, credentials and `.state` out of Git. Never delete
an uncertain operation checkpoint to get around a verification failure.

A receipt carrying a newer valid root-signed manifest requires explicit trust
refresh before verification; it never silently replaces the pinned manifest.
Signed deployment exports omit private lease proofs and identify their public
projection plus the original owner receipt digest.

## Trusted Git pipeline proof (CLI 0.32+)

An instance signature does not upgrade declared Git metadata. A trusted pipeline
can independently sign an existing Publication's exact retained author/record/
definition identities. The operator must explicitly authorize its public builder
key, issuer, repository, instance, Projects and Control Key principal.

```sh
woobe agent '@support' git-proof --revision REVISION_ID --commit COMMIT_SHA --repository owner/repository --publication PUBLICATION_UUID --resource-id AGENT_UUID --issuer pipeline --instance INSTANCE_UUID --workflow-run RUN_ID --project PROJECT_UUID --signing-key-file /private/ci-builder.seed --path git-proof.yaml
woobe agent AGENT_UUID git-attest --file git-proof.yaml --idempotency-key OPERATION_UUID
woobe project agent git-attestation get AGENT_UUID OPERATION_UUID
```

Uppercase values are placeholders. Equivalent Network commands are supported.
Proof generation is offline, compares regular Git blobs with the exact retained
author closure/canonical compiler, and writes a separate file after the commit.
Never place the seed, CLI Key or `.state` in Git. Configure a separate private CI
seed file; only its public key reaches the API. No builder is trusted by default.

`pipeline_signed_not_server_verified` is local; server `verified` means scoped
trusted-pipeline validation at acceptance. Neither command publishes or deploys
or rewrites the original Publication. On timeout inspect the original operation,
never repeat activation or create a replacement operation without knowing its
outcome. Builder revocation blocks new proofs, not immutable historical receipts.

Exact Git proofs resolve physical worktree paths on Windows/macOS and compare committed bytes. A line-ending conversion is a content change; preserve authored files with explicit Git attributes. Synchronous runtime output preserves integer identity and generation values without floating-point rounding.

The Git verifier ignores replacement refs and rejects corrupt Git objects. Use a clean exact checkout; a substituted commit is not accepted provenance.
