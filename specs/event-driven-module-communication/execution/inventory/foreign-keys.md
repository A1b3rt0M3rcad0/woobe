# Foreign Keys

Levantamento em: 2026-06-16

## Cross-module FKs (violações)

### billing/infra/database/models.py
- `ForeignKey("identity.organizations.id")` — **violação**: billing → identity
- `ForeignKey("identity.organizations.id")` — **violação**: billing → identity

### metering/infra/database/models.py
- `ForeignKey("core.projects.id")` — **violação**: metering → core (linha 19)
- `ForeignKey("core.projects.id")` — **violação**: metering → core (linha 33)
- `ForeignKey("core.projects.id")` — **violação**: metering → core (linha 53)

### observability/infra/database/models.py
- `ForeignKey("core.projects.id")` — **violação**: observability → core (linha 19)
- `ForeignKey("core.projects.id")` — **violação**: observability → core (linha 42)

### migrations/versions/0006_add_ask_jobs_table.py
- `sa.ForeignKey("core.projects.id")` — **violação**: migration com FK cross-module

## FKs intra-module (permitidas)

### agent/infra/database/models.py
Todas as FKs são `agent.*` → `agent.*` — permitidas

## Classificação

| FK | Origem | Destino | Local | Severidade | Spec |
|---|---|---|---|---|---|
| `identity.organizations.id` | billing/customers | identity | billing/models.py:35,48 | alta | 016 |
| `core.projects.id` | metering/* | core | metering/models.py:19,33,53 | alta | 016 |
| `core.projects.id` | observability/* | core | observability/models.py:19,42 | alta | 016 |
| `core.projects.id` | ask_jobs | core | migrations/0006:21 | alta | 017 |
