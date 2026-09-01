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

Every public function under `composition/composers/**` whose name ends in `_composer` is a short transactional composition root and must:

- be synchronous and contain wiring only;
- create exactly one configured `AgentUnitOfWork`;
- construct repositories explicitly with that same Unit of Work;
- never use Unit of Work repository/service-locator properties;
- return `TransactionalHandler` for request/response flows;
- return `StreamingTransactionalHandler` only when the database transaction is intentionally part of the stream lifecycle;
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

## Long-lived workflow composer contract

Agent execution is a workflow, not one database transaction. Long-lived entrypoints live under `composition/workflows/**` and return `WorkflowHandler`.

A workflow composer:

- never creates a global Unit of Work around the complete Agent Run;
- never receives or propagates `AsyncEngine`, `AsyncSession`, `async_sessionmaker` or `DATABASE_ENGINE`;
- composes explicit short-lived persistence boundaries for prepare, RAG persistence/search, Tool secret reads, finalization, failure and cancellation;
- keeps LLM, embedding, HTTP Tool and MCP execution outside database transactions;
- remains synchronous wiring only.

The executable transaction-boundary rules are:

- `ARCH-UOW-006`: SQLAlchemy engine/session types cannot escape into runtime, application, presentation or workflow composition;
- `ARCH-UOW-007`: long-lived runtime layers cannot construct `AgentUnitOfWork` internally;
- `ARCH-UOW-008`: `DATABASE_ENGINE` may only be consumed to construct `AgentUnitOfWork`; passing it to a runtime/service/factory is forbidden;
- `ARCH-WORKFLOW-001`: declared long-lived runtime composers must terminate in `WorkflowHandler` and cannot own a global UoW.

The canonical runtime shape is:

```text
Agent Run
  |
  +-- prepare transaction ---- commit
  |
  +-- RAG binding transaction - commit
  +-- embedding provider ------- no DB transaction
  +-- vector search transaction - commit
  |
  +-- LLM / Tool / MCP --------- no DB transaction
  |
  +-- finalize transaction ----- commit

failure/cancellation
  +-- dedicated short transaction
```

`DATABASE_ENGINE` is a process resource owned by composition. For HTTP/runtime flows it terminates at `AgentUnitOfWork` construction and is never injected into long-lived execution objects.

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
