# Changelog

All notable user-visible changes to Woobe SDK are recorded in this file.

The format follows Keep a Changelog conventions and versions follow the Python package version declared in `pyproject.toml`.

## Unreleased

## [0.1.0] - 2026-09-24

First public release of the Woobe Python SDK.

### Added

- Python client for consuming published Woobe Agents and Agent Networks through the Runtime API.
- Lazy `Chat` execution model with async semantic event streaming over Runtime Protocol v2.
- Canonical `WoobeEvent` envelopes with Run, Session, Run kind, sequence and occurrence metadata.
- Session reuse for conversational continuity when supported by the published target.
- External Context forwarding at Run creation with authoritative Runtime Acceptance validation.
- Unified Output Contract and External Context contract preflight validation from Pydantic models or JSON Schema.
- Typed terminal `ChatResult` projection with answer, structured output, usage, sources, Tool calls, fallback data, execution diagnostics, provider/model identity and Release metadata.
- Safe Run reattach after transport interruption, including sequence-gap recovery and duplicate-Run prevention.
- Agent and Network support through the same public client surface.
- Python 3.11, 3.12 and 3.13 validation in CI.
- MIT licensing and package/release governance for public distribution.

### Fixed

- External Context schema strictness now matches Runtime contract semantics.
- Local JSON Schema references are normalized for contract validation.
- Malformed contract-validator responses fail closed.
- SSE responses avoid compression behavior that can interfere with realtime streaming.

### Compatibility

- Requires Python 3.11 or newer.
- Direct runtime dependencies are `httpx>=0.28,<1` and `pydantic>=2.10,<3`.
- The SDK is pre-1.0; public APIs may still evolve before 1.0.0.
