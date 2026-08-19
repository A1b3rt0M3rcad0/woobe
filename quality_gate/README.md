# Woobe Quality Gate

`quality_gate/architecture` enforces executable architecture boundaries for bounded contexts migrated to the Woobe architecture contract.

Each governed bounded context owns one TOML policy under `quality_gate/architecture/policies/`. The checker is generic: new modules add policy data rather than module-specific branches in the checker.

The first governed module is `agent`. The policy is intentionally strict and is the acceptance criterion for the current refactor: the refactor is complete only when the architecture checker reports zero violations.

## Canonical dependency direction

The Agent module follows this dependency graph:

```text
entrypoint -> composition -> presentation
                     |----> application -> domain
                     |----> infra -------> domain
                                   ^
                                   |
                         application ports
```

`composition` is the only module layer allowed to wire concrete implementations. `presentation`, `application`, `infra` and `domain` must never import `composition`. Cross-bounded-context imports are forbidden by default.

## Transactional composer contract

Every public function under `composition/composers/**` whose name ends in `_composer` is an executable composition root and must:

- be synchronous and contain wiring only;
- create exactly one configured `AgentUnitOfWork`;
- construct repositories explicitly with that same Unit of Work;
- never use Unit of Work repository/service-locator properties;
- return `TransactionalHandler` for request/response flows;
- return `StreamingTransactionalHandler` for `*_stream_composer` flows;
- pass the same Unit of Work instance to the wrapper;
- contain no control flow, nested runtime helpers, async work or operational configuration loading;
- expose no SQLAlchemy/FastAPI/Starlette/LangChain framework types in its imports or signature.

The key semantic rules are:

- `ARCH021`/`ARCH023`: regular and streaming handler return contracts;
- `ARCH022`/`ARCH024`/`ARCH025`: composition-only execution and one transaction boundary;
- `ARCH027`/`ARCH028`: no control flow or nested runtime helpers in composers;
- `ARCH029`/`ARCH030`/`ARCH031`: no UoW service locator, framework-shaped parameters or configuration loading;
- `ARCH032`-`ARCH034`: framework-neutral Unit of Work contract and transaction-only concrete UoW;
- `ARCH035`-`ARCH039`: framework-neutral repository ports, explicit port implementation, no repository transaction control and UoW-based repository construction;
- `ARCH040`: application dependencies must declare explicit application-owned port types.

## Repository and Unit of Work policy

Application owns repository ports. Infrastructure implements them. Concrete repositories receive the Unit of Work and obtain their session only inside infrastructure. Repositories may flush/refresh but may not commit, rollback, create sessions or open transactions.

The shared Unit of Work contract is framework-neutral and exposes transaction lifecycle only. Concrete infrastructure UoWs may expose a session for infrastructure repositories, but must not own or locate repositories.

## Running the gate

```bash
uv run pytest -q tests/quality_gate
uv run python -m quality_gate.architecture.checker
```

The `Quality Gate` GitHub Actions workflow runs for pull requests targeting `development` whenever governed source, policy, gate tests or dependencies change.

Policies have no architecture allowlist for the governed Agent module. A violation is fixed in source or changed explicitly as an architectural decision; it is not suppressed to make CI green.
