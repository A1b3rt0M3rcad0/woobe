# SDK Change Guide

Use the narrowest change path that satisfies the requested behavior.

## Public API change

Read:

- `README.md`;
- `docs/ARCHITECTURE.md`;
- `docs/agents/INVARIANTS.md`;
- `tests/test_public_api.py`.

Check whether the behavior is genuinely new rather than an alias for an existing operation. Update README/examples/changelog when user-facing semantics change.

## Chat, Run or Session behavior

Primary file: `src/woobe/chat.py`.

Also review:

- `docs/RUNTIME_STREAMING.md`;
- `tests/test_chat.py`;
- private HTTP/SSE transport only when the behavior crosses that boundary.

Mandatory questions:

1. Can this create a duplicate logical Run?
2. Can identity change after Acceptance?
3. Can sequence ordering be corrupted?
4. Does recovery reattach the canonical Run?

## Runtime Protocol or event change

Primary files:

- `src/woobe/events.py`;
- `src/woobe/chat.py`;
- `src/woobe/_transport/sse.py`.

Do not loosen canonical event validation merely to accept malformed or legacy envelopes. Keep transport/control frames separate.

Add regression tests for full event identity and sequence semantics.

## Contract validation change

Primary files:

- `src/woobe/contracts.py`;
- `src/woobe/targets.py`;
- `src/woobe/_transport/http.py`.

Remember that schema preflight is client ergonomics; the published Woobe Release and Runtime Acceptance remain authoritative.

Test Pydantic and raw JSON Schema inputs where relevant.

## HTTP or authentication change

Primary file: `src/woobe/_transport/http.py`.

Keep Runtime Keys out of error text/logging. Do not disable TLS verification or redirect authorization behavior casually.

If retry behavior changes, prove that create operations remain duplicate-safe.

## SSE parser change

Primary file: `src/woobe/_transport/sse.py`.

Test split frames, multiline data, malformed input, control frames and cursor/sequence handling as relevant.

Parser convenience must not weaken semantic event validation.

## Result model change

Primary file: `src/woobe/results.py`.

Keep terminal result projection additive to the event stream and forward compatible with additive Runtime payload fields.

Update README examples if the public result surface changes.

## Packaging or dependency change

Primary file: `pyproject.toml`.

Run:

```bash
python -m build
twine check dist/*
```

Review `LICENSE.md`, `THIRD_PARTY_NOTICES.md` and release artifact contents for new distribution obligations.

## Release automation change

Read `RELEASING.md` and `docs/PUBLIC_RELEASE_CHECKLIST.md`.

Keep tag/version matching strict. Do not make published tags mutable. Prefer PyPI Trusted Publishing over long-lived API tokens.

## Documentation-only change

Update the canonical document rather than duplicating rules into several files. If a path/policy changes, update `AGENTS.md` or `docs/README.md` indexes in the same change.
