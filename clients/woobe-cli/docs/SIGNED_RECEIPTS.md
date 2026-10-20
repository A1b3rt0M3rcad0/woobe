# Signed ASaC receipts and offline trust

Use CLI 0.31+ and a Woobe instance with receipt signing configured. Export reads
an authorized immutable owner record. It does not publish, evaluate or activate
anything, and does not rewrite an operation or revision.

```sh
woobe agent UUID receipt publication PUBLICATION_UUID --path publication.yaml
woobe network UUID receipt deployment DEPLOYMENT_UUID --env production --path deployment.yaml
```

Categories are `revision`, `evaluation`, `publication` and `deployment`.
Use a revision ID for `revision`; the other categories use receipt UUIDs.
Native UUIDs work without `.woobe-config`; registered aliases also work.
YAML destinations use readable block YAML; `.json` preserves JSON. Existing
files, including symlink destinations, are never overwritten. Outputs and input
sizes are bounded. A backend without signing configuration rejects the request
explicitly rather than exporting a supposedly verified receipt.

## Establish trust separately

Obtain the **root fingerprint from the instance operator through a trusted
channel**. A fingerprint printed by an untrusted API is not sufficient.
The placeholder below must be replaced with that `sha256:...` value.

```sh
woobe trust pin publication.yaml --root-fingerprint ROOT_FINGERPRINT --path trust.yaml
woobe receipt verify publication.yaml --trust trust.yaml
```

Pinning verifies the root-signed key manifest before writing a new public trust
file. Verification is offline, does not need login or development configuration,
and validates the signature, exact typed payload, instance, resource scope,
key validity, revocation, manifest expiry and issue time. It rejects ambiguous
JSON/YAML, changed bytes, substituted roots and unknown keys.

A valid signature authenticates the server's owner record. It does not confer
permissions, claim that its Release is still selected, prove object availability
or upgrade a **declared** Git commit to verified provenance. The result reports
`trust_epoch` and `trust_expires_at`; current selection remains `not_observed`.

## Rotation and revocation

The offline operator increments the trust epoch, signs a new key manifest and
deploys that public manifest with a new online receipt key. Retired keys remain
valid for receipts issued within their historical validity interval. Revoked
keys reject even historical receipts. An expired manifest requires refresh.

Export a fresh receipt and verify its embedded updated manifest against the
existing pinned root:

```sh
woobe trust refresh fresh-publication.yaml --trust trust.yaml --path trust-next.yaml
```

Review the new epoch, expiry and key statuses, then replace the old public trust
file through your normal reviewed file/Git workflow. Refresh never overwrites
it silently. Same-epoch changes, lower epochs, another instance or another root
are rejected. Root replacement requires a new out-of-band fingerprint and an
explicit new pin. An expired old manifest may authenticate a refresh; it cannot
be used to verify new receipts until refreshed.

Offline verification cannot discover a revocation issued after the pinned
manifest. Refresh before sensitive use and retain the reported watermark.
Neither root seeds, online seeds, credentials nor private checkpoints belong in
Git. Only public pins/manifests and sanitized signed owner receipts are portable.

A receipt carrying a newer valid root-signed manifest requires explicit trust
refresh before verification; it never silently replaces the pinned manifest.
Signed deployment exports omit private lease proofs and identify their public
projection plus the original owner receipt digest.
