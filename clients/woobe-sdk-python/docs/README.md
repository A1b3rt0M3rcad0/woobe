# Woobe SDK Documentation

This directory contains the canonical engineering and runtime-contract documentation for Woobe SDK.

## Core documentation

- [Architecture](ARCHITECTURE.md) — package boundaries and client/runtime responsibility.
- [Runtime streaming](RUNTIME_STREAMING.md) — Runtime Protocol v2, SSE, sequence and reattach behavior.
- [Upgrading](UPGRADING.md) — package compatibility and migration guidance.
- [Public release checklist](PUBLIC_RELEASE_CHECKLIST.md) — final package/release verification.

## Coding-agent documentation

- [Domain index](agents/DOMAIN_INDEX.md) — code ownership and where changes belong.
- [Cross-cutting invariants](agents/INVARIANTS.md) — rules that must remain true across the SDK.
- [Change guide](agents/CHANGE_GUIDE.md) — routing and validation guidance by change type.

Repository-level contribution, licensing, security and release policies live at the repository root. Start with [../AGENTS.md](../AGENTS.md) when using a coding agent.
