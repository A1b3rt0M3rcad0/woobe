# Instance-signed ASaC receipts

Agent and Network remain the lifecycle authorities. Their signed-receipt GET
reads an authorized owner record and wraps its exact result in an Ed25519
attestation. The original revision, evaluation, publication, deployment and
operation IDs/digests are unchanged. This endpoint cannot sign a client-supplied
record. Incomplete operations require reconciliation before attestation.

Routes:

- `/projects/{project_id}/agents/{resource_id}/asac/signed-receipts/{category}/{receipt_id}`
- `/projects/{project_id}/networks/{resource_id}/asac/signed-receipts/{category}/{receipt_id}`

Categories are `revision`, `evaluation`, `publication`, `deployment`. Read
permission and scope remain those of the owner: Draft for revisions, Staging
for evaluation/publication, and the exact `environment` query for deployments.
The envelope adds stable instance/project/resource identity, category, signing
key identity and issue time. Type-tagged ASaC canonicalization preserves Unicode,
null/absence, array order and exact numbers. Signature scopes are distinct:
`trust-manifest` and `signed-receipt`. Shared Python/Go fixtures verify parity.

## Provision offline trust

Choose a stable instance UUID. Run the provisioning tool on an **offline
operator machine**, outside the repository. The example validity dates must be
chosen for your operational renewal schedule.

```sh
python scripts/asac_trust.py init \
  --directory /private/woobe-trust-1 \
  --instance 00000000-0000-4000-8000-000000000001 \
  --expires-at 2027-01-01T00:00:00Z \
  --key-until 2027-01-02T00:00:00Z
```

The new directory contains an offline `root.seed`, online `receipt.seed`, public
`trust.json` and private `online.env`. Existing directories/files are never
overwritten. Private files are mode 0600 on POSIX. Output prints public
fingerprints and paths only. Keep the root seed on the offline operator machine;
never deploy it, print it, commit it, or mount its directory into the API.

Transfer **only** the online configuration through your deployment secret
manager. API settings are:

- `WOOBE_ASAC_SIGNING_RECEIPT_PRIVATE_KEY`: online Ed25519 seed, canonical unpadded URL-safe base64.
- `WOOBE_ASAC_SIGNING_TRUST_MANIFEST`: JSON public manifest signed by the offline root.

The API holds no root private key. It verifies the configured manifest signature,
instance UUID, bounded monotonic epoch, exact key identities, validity intervals
and active online key. Startup does not invent keys or derive them from JWT or
encryption secrets. Unconfigured/invalid/expired authority returns an explicit
`ASAC_SIGNATURES_UNAVAILABLE`; it does not label an unsigned receipt verified.

Provide the root fingerprint independently to clients. CLI pinning requires
that operator-confirmed value; a fingerprint received only from an untrusted API
cannot establish trust. Public pins/manifests may be versioned through a reviewed
workflow. Keys, private environment files and credentials must remain private.

## Rotate, retire and revoke

Provision into a new directory using the original offline root and previous
public manifest. This allocates a new online key, increments the trust epoch,
retires previous active keys and optionally revokes specified key fingerprints.

```sh
python scripts/asac_trust.py rotate \
  --directory /private/woobe-trust-2 \
  --root-key /private/woobe-trust-1/root.seed \
  --manifest /private/woobe-trust-1/trust.json \
  --expires-at 2027-04-01T00:00:00Z \
  --key-until 2027-04-02T00:00:00Z
```

Use repeatable `--revoke sha256:...` for compromised previous keys. Deploy only
the new online configuration. Retired keys validate receipts issued in their
historical intervals; revoked keys reject even historical receipts. Clients
explicitly refresh the root-signed manifest. Lower epochs, same-epoch changes,
instance substitution and root substitution are rejected. Root replacement
requires independent approval of its new fingerprint; it is not ordinary
rotation. Renew before manifest/key expiry.

Offline verification states the trust epoch and expiry. It cannot observe a
later revocation without refresh and cannot prove current environment selection,
object availability, grants or Git provenance. A signed **declared** Git claim
remains declared. Authenticating server records is separate from validating a
trusted pipeline's relationship between commit and executable definition.

Signed deployment exports use an explicit public-owner-deployment@1 projection.
Private lease IDs/workflow/fencing proofs are omitted. The original immutable
owner receipt digest is retained as owner_receipt_digest; the signature verifies
the public projection, not a reconstruction of private operational evidence.
The underlying owner receipt, operation and audit are not rewritten.
