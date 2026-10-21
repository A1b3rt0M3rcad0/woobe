# Upgrading Woobe SDK

Woobe SDK is currently pre-1.0. Public APIs are intentionally kept small, but incompatible changes can still occur while the runtime contract stabilizes.

## Before upgrading

Review:

1. the target version section in `CHANGELOG.md`;
2. breaking/migration notes in the GitHub Release;
3. minimum Python and dependency requirements in `pyproject.toml`;
4. Runtime compatibility notes when protocol behavior changed.

For production applications, pin an exact SDK version or a deliberately bounded compatible range rather than consuming arbitrary future pre-releases.

## Public compatibility surface

The supported application-facing surface is the documented package-root/API behavior, including:

- `Woobe`;
- Agent and Network target connection;
- contract validation methods;
- `Chat`;
- `WoobeEvent`;
- typed result/error objects documented as public.

Modules under `src/woobe/_transport/` are private implementation and may change without compatibility guarantees.

## Upgrade procedure

In a clean branch:

```bash
python -m pip install --upgrade "woobe-sdk==<VERSION>"
pytest
```

Then validate the application's actual Runtime path, especially when the release changes streaming, protocol validation, contract handling or retry/reattach behavior.

## Streaming-sensitive upgrades

For changes involving SSE or Runtime Protocol v2, verify:

- semantic event envelopes still match application expectations;
- Session/Run identity is preserved;
- sequence handling does not duplicate or skip application-visible effects;
- reconnect reattaches the same canonical Run;
- terminal result projection still matches the terminal event.

Do not work around a compatibility problem by retrying create requests in a way that can duplicate Runs.

## Contract-sensitive upgrades

If output or External Context contract handling changed, compare the application's local Pydantic/JSON Schema declarations against the published Woobe Release before rollout.

The Runtime remains authoritative for Acceptance-time External Context validation.

## Breaking changes before 1.0

A pre-1.0 release may intentionally break public behavior. Such a release must describe the old behavior, the new behavior and the required application migration.

Silent breaking changes are defects in the release process.
