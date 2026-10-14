# Project configuration authority

Status: implementation in progress. This decision is not a claim that legacy
cutover or package migration is complete.

Project Environment owns active values. Agent-owned connections retain stable
IDs and typed references; Core owns declarations, environment slots, versions,
use policies, aliases, leases and validation evidence. Hosts connect the owners
through public ports. Agent does not import Core persistence.

| Decision | Contract |
| --- | --- |
| D01 | One central authority for active values; source clearing and alias creation must commit together. |
| D02 | Declare without a value; save structure before external preparation. |
| D03 | Preserve ProviderCredential, Model, Agent and Tool identity. |
| D04 | Typed references only in declared authentication fields; no global interpolation of secrets. |
| D05 | Server selects Project and Environment from accepted operations. |
| D06 | Missing Draft or Staging values never fall back to another Environment. |
| D07 | Legacy aliases choose explicit compatibility routes; new direct references cannot use those routes. |
| D08 | Administrative read responses expose metadata, never plaintext or ciphertext. |
| D09 | Backend dependency readers and the Core resolver define readiness for every client. |
| D10 | Only the selected target's exact dependency closure blocks that target. |
| D11 | Reading readiness performs no decryption or external calls; testing a connection is explicit. |
| D12 | Material versions are independent of immutable resource definitions and release signatures. |
| D13 | Owner transactions enforce permissions; hiding a form is not an authorization mechanism. |
| D14 | Configuration readiness does not grant Production deployment authority. |
| D15 | Existing Woobe controls, spacing and theme tokens remain the UI contract. |

Run acceptance pins value and policy identities in its transaction. Queues carry
references only. Workers resolve pinned material immediately before each actual
outbound request; a retry or redirect cannot change the approved destination.
Rotation preserves accepted versions for bounded retention. Revocation denies
further use. A live lease protects its archived versions from cleanup.

Provider and MCP discovery authorize and pin in a short transaction, perform
network I/O after commit, then retain metadata-only evidence. MCP discovery
rechecks authority and the Tool revision before saving its result. Merely opening
Environments or declaring a Tool cannot initiate discovery.

Changing a binding uses its own revision. A compare-and-swap conflict requires
review. Legacy inline material must not be discarded as a side effect of binding
an existing connection; transfer and route conversion are explicit operations.

Metadata readers batch keys, values, policies and validation evidence. Policy
matching is indexed by key and consumer in memory, avoiding a full policy scan
for each dependency. External validation is separate from material state and
becomes stale after a relevant version or policy change.

The planned migration boundary requires a verified bridge fleet and drained
incompatible processes before source cutover. Empty/corrupt sources remain
missing/unavailable. Signed historical bytes must not be rewritten as if their
signature covered a sanitized projection. Rollback after cutover requires a
bridge reader, never restoration of stale inline material.
