# Contributing to Woobe SDK

Woobe SDK uses `master` as the integration branch.

## Workflow

1. Create a focused branch from the latest `master`.
2. Keep the change scoped to one SDK concern.
3. Preserve the documented public API unless the change intentionally changes that contract.
4. Add or update tests for behavior you change.
5. Update documentation when public behavior, protocol expectations, packaging or compatibility changes.
6. Run the relevant quality checks.
7. Open a pull request targeting `master`.
8. Merge only after the required review and checks succeed.

Recommended branch prefixes are `feature/`, `fix/`, `chore/`, `docs/` and `ci/`.

## Commit messages

Repository-authored commits and pull-request titles use Conventional Commits:

```text
<type>(<scope>): <description>
```

Preferred types are `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore` and `revert`.

Useful scopes include `client`, `targets`, `chat`, `streaming`, `contracts`, `events`, `results`, `transport`, `docs`, `repo` and `release`.

Examples:

```text
feat(contracts): add typed validation result
fix(streaming): reattach the canonical run after sequence gap
docs(releasing): document PyPI publication flow
ci(release): validate package metadata before publish
chore(repo): establish SDK repository governance
```

Breaking changes use `!` or a `BREAKING CHANGE:` footer.

## SDK boundary

The SDK is a client for the Woobe Runtime API. It is not a second control plane and not an Agent framework.

Keep these responsibilities server-side in Woobe:

- Agent and Network orchestration;
- model/provider selection;
- Tool and MCP execution;
- Knowledge/RAG;
- Context Engineering;
- execution strategy semantics;
- Release/environment rules;
- Run finalization and durable runtime truth.

The SDK owns client-side concerns such as Runtime Key authentication, request serialization, schema preflight, SSE parsing, protocol validation, safe reattach, bounded transport retry and typed public results.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/agents/INVARIANTS.md](docs/agents/INVARIANTS.md) before changing runtime behavior.

## Runtime invariants

A connection observes a Run; it does not own it. Once the canonical Run ID is known, recovery must reattach to that same Run rather than create another logical execution.

Do not add automatic retry behavior that can duplicate a Run. A create retry is valid only when the server exposes an idempotency contract that makes the retry the same logical operation.

The SDK must not rename or reinterpret canonical Woobe runtime event semantics. `WoobeEvent` represents Runtime Protocol v2 rather than a parallel SDK event model.

Transport/control frames are not semantic Run events and must not be fabricated into `WoobeEvent`.

## Public API discipline

Keep the main application surface small:

```python
woobe = Woobe()
agent = woobe.connect.agent(alias="support", key="...")
chat = agent.chat(input="Olá")

async for event in chat.events():
    ...
```

Do not add aliases such as `ask()`, `send()`, `invoke()`, `execute()` or `complete()` for the same operation without materially different semantics.

Anything under `src/woobe/_transport/` is private implementation. Do not expose HTTP response objects, SSE parser internals or server storage details through the public API.

## Compatibility

The package is pre-1.0. Breaking changes are still possible, but they must be intentional, documented in `CHANGELOG.md`, represented by the selected version and accompanied by migration guidance when users need to change code.

Additive Runtime payload fields should remain forward compatible when the SDK can safely preserve them.

See [docs/UPGRADING.md](docs/UPGRADING.md).

## Quality

Run:

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
python -m build
twine check dist/*
```

Do not claim a check passed unless it was actually executed.

Tests should be placed at the narrowest useful level. Protocol, duplicate-Run, sequence and public-API behavior should have regression coverage.

## Dependencies and third-party material

Keep runtime dependencies small. A new runtime dependency must solve a concrete SDK concern that is not reasonably handled by the standard library or an existing dependency.

Review provenance and license compatibility before adding third-party code, assets or dependencies. Update [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when released artifacts gain notice or attribution obligations.

## Licensing and contributions

Woobe SDK is distributed under the MIT License. Unless a file states otherwise, contributions submitted to this repository are accepted under the same MIT terms.

By submitting a contribution, you represent that you have the right to submit it under those terms. The repository does not require the Woobe platform CLA for ordinary SDK contributions.

The MIT license for this SDK does not relicense the Woobe platform, server-side Core code, Enterprise code or Woobe trademarks. See [LICENSING.md](LICENSING.md) and [TRADEMARKS.md](TRADEMARKS.md).

## Security

Runtime Keys and credentials are secrets. Do not publish keys, access tokens, customer data, private endpoints or non-public vulnerability details in issues or pull requests.

Security reports must follow [SECURITY.md](SECURITY.md).
