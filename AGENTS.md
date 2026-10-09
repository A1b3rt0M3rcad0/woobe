# AGENTS.md

This file is the entry point for coding agents working in the Woobe repository.

Keep this file small. It is an index and routing guide, not a duplicate of product, architecture, testing, licensing or release documentation.

## Start here

- Product overview: [README.md](README.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Domain ownership index: [docs/agents/DOMAIN_INDEX.md](docs/agents/DOMAIN_INDEX.md)
- Cross-cutting invariants: [docs/agents/INVARIANTS.md](docs/agents/INVARIANTS.md)
- Change routing guide: [docs/agents/CHANGE_GUIDE.md](docs/agents/CHANGE_GUIDE.md)
- Contribution and commit policy: [CONTRIBUTING.md](CONTRIBUTING.md)
- Release procedure: [RELEASING.md](RELEASING.md)
- Test topology: [docs/testing/COMPOSE_TESTS.md](docs/testing/COMPOSE_TESTS.md)
- Self-hosting: [docs/SELF_HOSTING.md](docs/SELF_HOSTING.md)
- Upgrade guidance: [docs/UPGRADING.md](docs/UPGRADING.md)
- Licensing model: [LICENSING.md](LICENSING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Architecture decisions: [docs/adr/](docs/adr/)

## Topic-specific documentation

- Control Plane authority: [docs/security/CONTROL_PLANE.md](docs/security/CONTROL_PLANE.md)

- Runtime streaming: [docs/runtime/STREAMING.md](docs/runtime/STREAMING.md)
- Signed ASaC receipts and instance trust: [docs/runtime/ASAC_SIGNED_RECEIPTS.md](docs/runtime/ASAC_SIGNED_RECEIPTS.md)
- ASaC history and portable digests: [docs/runtime/ASAC_HISTORY.md](docs/runtime/ASAC_HISTORY.md)
- Unified runtime observer: [docs/runtime/UNIFIED_OBSERVER.md](docs/runtime/UNIFIED_OBSERVER.md)
- ChatSurface: [docs/runtime/CHAT_SURFACE.md](docs/runtime/CHAT_SURFACE.md)
- MCP Tools: [docs/runtime/MCP_TOOLS.md](docs/runtime/MCP_TOOLS.md)
- Provider contributions: [docs/CONTRIBUTING_PROVIDERS.md](docs/CONTRIBUTING_PROVIDERS.md)
- Runbooks: [docs/runbooks/](docs/runbooks/)
- Performance: [docs/performance/](docs/performance/)

## Working rule

Before changing code, identify the owning domain/package through the domain index, read the relevant canonical documentation and existing tests, then follow the change guide.

Do not duplicate durable domain semantics in this file. When a referenced path or policy changes, update this index in the same change.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
