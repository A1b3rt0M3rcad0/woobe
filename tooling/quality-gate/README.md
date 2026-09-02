# Woobe Quality Gate

`tooling/quality-gate` contains repository architecture checks and declarative policies. It is engineering tooling and is not part of the production runtime dependency graph.

The installable Python package uses src layout at `tooling/quality-gate/src/quality_gate`. Every bounded context under `packages/woobe-core/src/modules/` must own:

- one architecture policy under `architecture/policies/<module>.toml`;
- one responsibility contract under `architecture/responsibilities/<module>.toml`;
- one transaction-ownership contract under `architecture/policies/contracts/<module>_transaction_ownership.toml`.

Runtime-heavy modules may additionally define a `<module>_runtime_transaction_boundaries.toml` contract.

The checker is generic. Module-specific rules live in declarative policy data instead of module-specific branches in the checker.

## Canonical module dependency direction

Agent is the reference architecture for Core bounded contexts:

```text
entrypoint -> composition -> presentation
                     |----> application -> domain
                     |----> infra -------> domain
                                   ^
                                   |
                         application interfaces
```

The target module shape is:

```text
modules/<module>/
├── domain/
├── application/
│   ├── dtos/
│   ├── interfaces/
│   └── use_cases/
├── infra/
├── composition/
│   ├── composers/
│   ├── resources.py
│   ├── module.py        # when the module exposes a wider composed surface
│   └── workers.py       # when the module owns workers
├── presentation/
│   ├── controllers/
│   └── http/
└── entrypoint.py
```

FastAPI remains module-local during this refactor, but it is constrained to `presentation/http/**`. HTTP is a transport adapter, not a composition root.

`composition` is the only module layer allowed to wire concrete implementations. `presentation`, `application`, `infra` and `domain` must never import `composition`.

## Woobe Core service isolation

Every bounded context under `packages/woobe-core/src/modules/` is an independent service boundary.

A module must not import another module. This includes imports through another module's `entrypoint.py`: entrypoints are public surfaces for consumers outside that service boundary, not an exception that allows in-process coupling between Woobe Core services.

Cross-service orchestration must live outside `packages/woobe-core/src/modules/`, such as in `woobe-api`, `woobe-workers`, or another explicit external composition root. Modules may depend on approved `shared.*` contracts and infrastructure according to their own policy, but communication with another service must happen through explicit contracts/transports rather than direct Python imports of that service implementation.

`ARCH008` enforces the source-level rule. Repository self-tests also ratchet every Woobe Core module policy so `forbid_cross_module_imports` cannot be disabled and another module cannot be reintroduced through an allowlist exception.

## Transactional composer contract

Every public function under `composition/composers/**` whose name ends in `_composer` is a short transactional composition root and must:

- be synchronous and contain wiring only;
- create exactly one configured module Unit of Work;
- construct repositories explicitly with that same Unit of Work;
- never use Unit of Work repository/service-locator properties;
- return `TransactionalHandler` for ordinary request/response flows;
- return `StreamingTransactionalHandler` only when the transaction is intentionally part of the bounded stream lifecycle;
- pass the same Unit of Work instance to the wrapper;
- contain no control flow, nested runtime helpers, async work or operational configuration loading;
- expose no SQLAlchemy/FastAPI/Starlette framework types in its imports or signature;
- receive no dependencies or operation data as composer arguments.

Long-lived execution must not keep a database transaction open for the duration of provider/tool/network execution. Runtime-heavy modules use explicit runtime transaction-boundary contracts for this rule.

## Architectural ratchet

The policies are intentionally strict. During the module refactor the architecture command is expected to report violations until each bounded context reaches the target architecture.

A module is considered migrated only when its architecture policy, responsibility contract and transaction-boundary rules pass without suppressions added solely to make the gate green.

The quality gate also verifies coverage: adding a new Core bounded context without architecture, responsibility and transaction-ownership contracts fails the self-tests.

## Running the gate

From the repository root:

```bash
uv run pytest -q tests/quality_gate

PYTHONPATH=tooling/quality-gate/src \
  uv run python -m quality_gate.architecture.checker \
  --policy-dir tooling/quality-gate/src/quality_gate/architecture/policies
```

The GitHub Actions `Quality Gate` workflow runs the same commands. Policy violations are fixed in source or changed explicitly as an architecture decision; they are not suppressed merely to make CI green.
