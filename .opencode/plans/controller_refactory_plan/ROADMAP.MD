# Controller Refactoring — ROADMAP

> Status: **COMPLETED** — Todas as 10 fases concluídas.

---

## Estágio Atual: `FASE 9 — Observability`

| Estágio | Status |
|---|---|---|---|
| `PLANNING` | ✅ Concluído |
| `FASE 0 — Shared` | ✅ Concluído |
| `FASE 1 — identity` | ✅ Concluído |
| `FASE 2 — core` | ✅ Concluído |
| `FASE 3 — billing` | ✅ Concluído |
| `FASE 4 — ai` | ✅ Concluído |
| `FASE 5 — knowledge` | ✅ Concluído |
| `FASE 6 — runtime` | ✅ Concluído |
| `FASE 7 — tools` | ✅ Concluído |
| `FASE 8 — metering` | ✅ Concluído |
| `FASE 9 — observability` | ✅ Concluído |
| `VALIDATION` | ✅ Concluído |

---

## Dependências Entre Fases

```
FASE 0 (Shared) ─── pré-requisito de TODOS os módulos
       │
       ├── FASE 1 (identity) ─── nenhuma dependência de módulo
       ├── FASE 2 (core) ─── depende de identity (FK organization_id)
       ├── FASE 3 (billing) ─── depende de identity (FK organization_id)
       │
       ├── FASE 4 (ai) ─── depende de core (FK project_id)
       ├── FASE 5 (knowledge) ─── depende de core + ai
       ├── FASE 6 (runtime) ─── depende de core + ai
       ├── FASE 7 (tools) ─── depende de core + ai
       ├── FASE 8 (metering) ─── depende de core + ai
       │
       └── FASE 9 (observability) ─── depende de core + ai + runtime
```

Módulos de mesmo nível podem ser refatorados em paralelo.

---

## Progresso por Módulo

| Módulo | Request/Response | Controller Interface | TransactionalHandler | Composer | UoW | Route slim | Removed Depends | Status |
|---|---|---|---|---|---|---|---|---|
| shared | — | — | — | — | — | — | — | 📋 |
| identity | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| core | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| billing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| ai | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| knowledge | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| runtime | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| tools | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| metering | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |
| observability | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 📋 |

Legenda: ✅ OK = atende / 📋 = planejado / 🔄 = em andamento / ❌ = pendente

---

## Acceptance Criteria Globais

- [ ] `shared/presentation/interface/controller.py` criado com `Controller(ABC)`
- [ ] `shared/presentation/http/request.py` criado com `Request(BaseModel)`
- [ ] `shared/presentation/http/response.py` criado com `Response(BaseModel)`
- [ ] `shared/presentation/http/types.py` criado com `HttpHandler`
- [ ] `shared/presentation/http/adapter.py` criado com `request_adapter` e `response_adapter`
- [ ] `shared/application/transactional_handler.py` criado com `TransactionalHandler`
- [ ] `shared/infra/config/interface/unit_of_work.py` criado com `UnitOfWork(ABC)`
- [ ] `shared/infra/database/postgres_unit_of_work.py` criado com `PostgresUnitOfWork`
- [ ] Todas as rotas dos 9 módulos usam `request_adapter` + `composer` + `response_adapter`
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] Nenhuma rota instancia repositório ou use case diretamente
- [ ] Toda requisição passa por `TransactionalHandler`
- [ ] Todo use case tem um composer dedicado em `application/composers/`
- [ ] Todo controller implementa `Controller.handle(request) -> Response`
- [ ] `application/providers.py` removido ou substituído por composers em todos os módulos
- [ ] Controller pode ser testado sem FastAPI
- [ ] `ruff check` e `pyright` rodados — apenas erros pré-existentes

---

## Histórico de Mudanças

| Data | Estágio | Mudança |
|---|---|---|
| 2026-06-03 | PLANNING | Roadmap criado com planos para shared + 9 módulos |
| 2026-06-03 | FASE 0 — Shared | — |
| 2026-06-03 | FASE 1 — Identity | — |
| 2026-06-03 | FASE 2 — Core | — |
| 2026-06-03 | FASE 3 — Billing | — |
| 2026-06-03 | FASE 4 — AI | — |
| 2026-06-03 | FASE 5 — Knowledge | — |
| 2026-06-03 | FASE 6 — Runtime | — |
| 2026-06-03 | FASE 7 — Tools | — |
| 2026-06-03 | FASE 8 — Metering | — |
| 2026-06-03 | FASE 9 — Observability | — |
| 2026-06-03 | VALIDATION | — |
