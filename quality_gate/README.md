# Woobe Quality Gate

`quality_gate/architecture` enforces executable architecture boundaries for modules that have been migrated to the Woobe architecture contract.

Each governed bounded context owns one TOML policy in `quality_gate/architecture/policies/`. The checker is generic: adding a module means adding a policy, not adding module-specific branches to the checker.

The first governed module is `agent`. Its policy follows the composition model used by the HostGator challenge: application owns contracts, infrastructure implements them, presentation controllers depend on contracts, routes enter through composition, and composition is the only layer allowed to wire concrete implementations.

## Transactional composer contract

For the Agent, every public function under `composition/composers/**` whose name ends in `_composer` is an executable composition root and must:

- be synchronous while composing dependencies;
- create exactly one configured `AgentUnitOfWork`;
- return `TransactionalHandler` for regular request/response flows;
- return `StreamingTransactionalHandler` for `*_stream_composer` flows;
- pass the same Unit of Work instance to the transactional wrapper;
- never open the Unit of Work with `async with` inside the composer itself.

Private helpers and factories that do not end in `_composer` are not transaction boundaries. They may support runtime assembly, but the public composer remains responsible for returning the governed wrapper.

The semantic checks are:

- `ARCH021`: regular composer return contract;
- `ARCH022`: composer must compose rather than execute async work or return a raw callable;
- `ARCH023`: streaming composer must return `StreamingTransactionalHandler`;
- `ARCH024`: composer cannot own the Unit of Work context manager;
- `ARCH025`: composer must create one Unit of Work and pass that same instance to the wrapper.

Run locally with:

```bash
uv run python -m quality_gate.architecture.checker
uv run pytest -q tests/quality_gate
```

The `Quality Gate` GitHub Actions workflow runs on pull requests targeting `development` whenever governed source, policies, gate tests, dependencies, or the workflow itself changes. A failing architecture policy blocks that CI check.

A policy is strict. Governed modules do not have architecture allowlists; a violation must be removed from the source or explicitly changed in the policy as an architectural decision.
