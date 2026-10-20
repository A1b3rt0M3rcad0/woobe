# AGENTS.md

This file is the entry point for coding agents working in the Woobe SDK repository.

Keep this file small. It is an index and routing guide, not a duplicate of architecture, protocol, testing, licensing or release documentation.

## Start here

- Product/API overview: [README.md](README.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Domain ownership index: [docs/agents/DOMAIN_INDEX.md](docs/agents/DOMAIN_INDEX.md)
- Cross-cutting invariants: [docs/agents/INVARIANTS.md](docs/agents/INVARIANTS.md)
- Change routing guide: [docs/agents/CHANGE_GUIDE.md](docs/agents/CHANGE_GUIDE.md)
- Runtime streaming contract: [docs/RUNTIME_STREAMING.md](docs/RUNTIME_STREAMING.md)
- Contribution policy: [CONTRIBUTING.md](CONTRIBUTING.md)
- Release procedure: [RELEASING.md](RELEASING.md)
- Upgrade guidance: [docs/UPGRADING.md](docs/UPGRADING.md)
- Licensing: [LICENSING.md](LICENSING.md)
- Security: [SECURITY.md](SECURITY.md)

## Working rule

Before changing code, identify the owning surface through the domain index, read the relevant canonical documentation and existing tests, then follow the change guide.

Do not turn the SDK into a second control plane or execution engine. Preserve the client/runtime boundary and the duplicate-Run safety invariants.

Do not duplicate durable semantics in this file. When a referenced path or policy changes, update this index in the same change.
