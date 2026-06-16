# Cross Module Imports

Levantamento em: 2026-06-16

## Imports dinâmicos cross-module (agent → metering, observability)

### agent/infra/adapters/metering_usage_recorder.py
- `importlib.import_module("modules.metering.domain.entities")` — **violação**: importa domain entities de outro módulo
- `importlib.import_module("modules.metering.domain.enums")` — **violação**: importa domain enums de outro módulo
- `importlib.import_module("modules.metering.infra.database.repositories")` — **violação**: importa repositories de outro módulo

### agent/infra/adapters/observability_trace_recorder.py
- `importlib.import_module("modules.observability.domain.entities")` (4 ocorrências) — **violação**
- `importlib.import_module("modules.observability.domain.enums")` (3 ocorrências) — **violação**
- `importlib.import_module("modules.observability.infra.database.repositories")` (4 ocorrências) — **violação**

### agent/application/use_cases/ask_agent_stream_service.py
- `importlib.import_module("modules.observability.infra.database.repositories")` — **violação**
- `importlib.import_module("modules.observability.domain.enums")` — **violação**

## Imports estáticos mesmomódulo (permitidos)

Todos os imports em `src/modules/agent/` de `modules.agent.*` são mesmomódulo e permitidos.
Todos os imports em `src/modules/billing/` de `modules.billing.*` são mesmomódulo e permitidos.
Todos os imports em `src/modules/metering/` de `modules.metering.*` são mesmomódulo e permitidos.
Todos os imports em `src/modules/observability/` de `modules.observability.*` são mesmomódulo e permitidos.
Todos os imports em `src/modules/identity/` de `modules.identity.*` são mesmomódulo e permitidos.
Todos os imports em `src/modules/core/` de `modules.core.*` são mesmomódulo e permitidos.

## Classificação

| Origem | Destino | Tipo | Severidade | Spec de correção |
|---|---|---|---|---|
| agent/infra/adapters/metering_usage_recorder | metering (domain, infra) | dinâmico | alta | 007-012 |
| agent/infra/adapters/observability_trace_recorder | observability (domain, infra) | dinâmico | alta | 007-015 |
| agent/application/use_cases/ask_agent_stream_service | observability (infra, domain) | dinâmico | alta | 009 |
