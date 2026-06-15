# 001 — Layer and Module Dependency Rules

## Allowed imports per layer

| Layer | May import from |
|---|---|
| `domain/` | Own module's `domain/`, standard library, `shared/domain/` (technical contracts only) |
| `application/` (or `service/`) | Own module's `domain/`, standard library, `shared/application/` or `shared/infra/` (technical contracts only) |
| `application/composers/` | Own module's `domain/`, `application/`, `service/`, `infra/`, standard library, `shared/` — composition root exception |
| `infra/` | Own module's `domain/`, `application/` (interfaces), standard library, `shared/infra/` |
| `presentation/` | Own module's `application/` (or `service/`), standard library, `shared/presentation/` |

## Forbidden imports

| Pattern | Reason |
|---|---|
| `from modules.<other>.domain import ...` | Cross-module domain access — coupling bounded contexts |
| `from modules.<other>.application import ...` | Cross-module application access |
| `from modules.<other>.infra import ...` | Cross-module infra access |
| `from modules.<other>.presentation import ...` | Cross-module presentation access |
| `from modules.<own>.infra import ...` in `presentation/` | Presentation bypassing application layer |
| `from modules.<own>.presentation import ...` in `domain/` | Domain depending on outer layer |
| `from modules.<own>.infra import ...` in `domain/` | Domain depending on infrastructure |
| `from modules.<own>.infra.models import ...` in `service/use_cases.py` or `application/use_cases/` | Business logic depending on database models |

## Allowlist exception mechanism

Temporary exceptions are registered in `tests/architecture/legacy_import_allowlist.yaml` with scope `layer_dependencies` and a `removal_spec` referencing the spec that will fix the violation.

## Module boundary rules

- Modules communicate only via Outbox/RabbitMQ/Inbox
- Direct `import modules.<other>.*` is forbidden
- Foreign Key references to tables owned by another module are forbidden
- External IDs are stored as opaque UUIDs without FK constraints

## Validation mechanism

AST-based static analysis via `tests/architecture/test_layer_dependencies.py` and `tests/architecture/test_module_boundaries.py`.
