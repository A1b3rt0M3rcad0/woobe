# SDK Domain Index

Use this index to identify the owning surface before changing code.

## Public client and connection

- `src/woobe/client.py` — `Woobe` client lifecycle, base URL configuration and client shutdown.
- `src/woobe/connect.py` — public target connection entry point.
- `src/woobe/targets.py` — Agent/Network target objects, chat construction and contract validation calls.

Typical tests: `tests/test_public_api.py`, `tests/test_http.py`, `tests/test_contracts.py`.

## Run observation and streaming semantics

- `src/woobe/chat.py` — lazy Run creation/observation, Session/Run identity, sequence handling, reattach and terminal result capture.
- `src/woobe/events.py` — canonical Runtime Protocol v2 semantic event model.
- `src/woobe/results.py` — typed terminal result projection and result submodels.
- `src/woobe/errors.py` — public SDK error taxonomy.

Typical tests: `tests/test_chat.py`, `tests/test_public_api.py`.

## Contract validation

- `src/woobe/contracts.py` — local schema normalization and typed contract-validation results.
- `src/woobe/targets.py` — target-scoped calls to the Runtime contract validator.

Typical tests: `tests/test_contracts.py`, `tests/test_http.py`.

## Private transport

- `src/woobe/_transport/http.py` — HTTP request construction, Runtime Key auth, Runtime endpoints and transport-level recovery calls.
- `src/woobe/_transport/sse.py` — SSE frame parsing and transport/control frame handling.

Typical tests: `tests/test_http.py`, `tests/test_sse.py`, plus `tests/test_chat.py` when transport behavior affects Run safety.

Everything under `_transport` is private implementation. Do not make application code depend on it.

## Documentation and examples

- `README.md` — primary application-facing SDK contract and quick start.
- `docs/ARCHITECTURE.md` — boundary and package architecture.
- `docs/RUNTIME_STREAMING.md` — streaming/protocol semantics.
- `examples/` — small executable public-API examples.

## Repository/release surfaces

- `pyproject.toml` — canonical package metadata and version.
- `.github/workflows/ci.yml` — compatibility and package quality gate.
- `.github/workflows/release.yml` — immutable tag-to-PyPI/GitHub release path.
- `RELEASING.md` — release procedure.
- `LICENSING.md`, `LICENSE.md`, `THIRD_PARTY_NOTICES.md`, `TRADEMARKS.md` — distribution/legal boundaries.

When a change spans several areas, preserve dependency direction: public/domain types may use private transport, but private transport must not invent product-domain semantics.
