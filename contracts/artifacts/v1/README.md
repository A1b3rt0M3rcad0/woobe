# Artifacts contract version 1

Canonical DTOs live in `modules.artifacts.application.contracts.api`, independent
of HTTP, processing adapters and process hosts. Generate schemas from the root:

```sh
.venv/bin/python scripts/generate_artifact_schemas.py
```

The JSON Schema 2020-12 files and positive/negative fixtures are shared input for
Python, Go and browser consumers. Requests reject unknown fields and unsupported
schema versions; additive response/event decoding is handled by each client.
Cross-field source/locator and revision-CAS invariants are also validated in the
canonical DTOs and domain. Schema validation alone does not authorize a resource
or prove a citation's meaning. Identifiers are opaque, not storage paths/URLs.

Physical PDF page indices are zero-based; display numbers are index + 1. Textual
representations use line/character locations without fabricated page numbers.
Sources bind exact revision and generation; node IDs require their exact index.
Discovery must list only capabilities actually wired in the selected environment.
Empty capability lists do not announce optional processors or transfer support.

The domain owns immutable originals, revision/source identities, index hierarchy,
provenance categories, bounded pagination, lifecycle states and nonnegative quota
accounting. Capability Protocols are contracts, not working adapters. Persistence,
authorization, processing and HTTP become available in subsequent plan steps.
