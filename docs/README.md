# Woobe documentation

`docs/` contains durable technical and operational documentation for the repository. Current system behavior belongs in topical documentation; durable architecture decisions belong in ADRs.

## Main areas

- `ARCHITECTURE.md` — current high-level product, package and runtime architecture.
- `SELF_HOSTING.md` and `UPGRADING.md` — operator guidance for Community installations.
- [`CLI.md`](CLI.md) — native installation, Workspace CLI Keys, contexts, manifests and runtime credentials.
- [`../RELEASING.md`](../RELEASING.md) — canonical platform release procedure and publication gates.
- `CONTRIBUTING_PROVIDERS.md` — provider contribution guidance.
- `adr/` — accepted/proposed Architecture Decision Records and their rationale.
- `agents/` — coding-agent routing guides, domain ownership index and cross-cutting invariants.
- `api/` — API-facing documentation and contracts.
- `runtime/` — runtime, streaming, ChatSurface and related execution documentation.
- `deployment/` — deployment-specific guidance.
- `testing/` — validation topology and test contracts.
- `runbooks/` — operational procedures and incident-oriented guidance.
- `performance/` — performance assumptions, measurements and operating guidance.

Documentation should describe the repository that exists now. Temporary implementation notes and work-in-progress planning belong in issues or pull requests rather than being treated as durable product documentation.

- `CLI_PACKAGES.md` — portable Agent/Network Package API, lifecycle and recovery.
- `testing/PACKAGE_ACCEPTANCE.md` — executable Package V1 acceptance matrix and paired qualification.
