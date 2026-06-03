# Repository Refactoring — ROADMAP

> Status: **COMPLETED** — Todas as 10 fases foram executadas e validadas.

---

## Estágio Atual: `COMPLETED`

| Estágio | Status |
|---|---|---|
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

| Módulo | Shared | Domain Interface | Concrete Repo | Pagination | Save Audit | Outbox | Status |
|---|---|---|---|---|---|---|---|---|
| shared | — | — | ✅ Concluído | ✅ Concluído | — | — | ✅ |
| identity | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK | ✅ |
| core | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK | ✅ |
| billing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK | ✅ |
| ai | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK | ✅ |
| knowledge | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Criado | ✅ |
| runtime | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Criado | ✅ |
| tools | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Criado | ✅ |
| metering | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK | ✅ |
| observability | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK | ✅ |

Legenda: ✅ OK = já atende / ❌ Ausente = precisa criar / 📋 = planejado

---

## Acceptance Criteria Globais

- [x] `BaseRepository` renomeado para `BaseSQLAlchemyRepository`
- [x] `self.session` → `self._session` (protegido)
- [x] Métodos técnicos são protegidos (`_add_model`, `_get_model_by_id`, `_delete_model`, `_flush`, `_refresh_model`)
- [x] `list_all()` removido — 3 consumers corrigidos
- [x] `_paginate_models()` implementado no base
- [x] Nenhuma interface de domínio importa SQLAlchemy
- [x] Nenhum repositório retorna ORM model para domain-facing
- [x] Todo list method paginável retorna `CursorPage[Entity]`
- [x] `save()` semantics auditadas por módulo (insert-only / upsert / merge)
- [x] `flush()`/`refresh()` padronizado por módulo
- [x] Nenhum `commit()` existe dentro de repositórios
- [x] Outbox writers existem em todos os 9 módulos
- [x] `ruff check` e `pyright` rodados — apenas erros pré-existentes
- [x] `knowledge`, `runtime`, `tools` ganham `SQLAlchemyOutboxEventWriter`

---

## Histórico de Mudanças

| Data | Estágio | Mudança |
|---|---|---|
| 2026-06-03 | PLANNING | Roadmap criado com planos para 10 módulos |
| 2026-06-03 | FASE 0 — Shared | BaseRepository → BaseSQLAlchemyRepository, métodos protegidos, list_all removido, _paginate_models implementado |
| 2026-06-03 | FASE 1 — Identity | 5 repositórios migrados para Dual + BaseSQLAlchemyRepository, CursorPage adicionado, save padronizado flush+refresh |
| 2026-06-03 | FASE 2 — Core | 2 repositórios migrados, CursorPage adicionado, flush+refresh padronizado |
| 2026-06-03 | FASE 3 — Billing | 4 repositórios migrados, métodos abstratos faltantes implementados, save semantics mantidas |
| 2026-06-03 | FASE 4 — AI | 2 repositórios migrados, CursorPage adicionado, save/update semantics documentadas |
| 2026-06-03 | FASE 5 — Knowledge | 4 repositórios Composition migrados, CursorPage adicionado, import corrigido, OutboxEventWriter criado |
| 2026-06-03 | FASE 6 — Runtime | 2 repositórios Composition migrados, CursorPage adicionado, OutboxEventWriter criado |
| 2026-06-03 | FASE 7 — Tools | 2 repositórios Composition migrados, CursorPage adicionado, OutboxEventWriter criado |
| 2026-06-03 | FASE 8 — Metering | UsageEvent (Dual) migrado, UsageDaily* paginação manual por day, merge semantics preservadas |
| 2026-06-03 | FASE 9 — Observability | 2 repositórios Dual migrados, self.session.get() → _get_model_by_id, CursorPage adicionado |
| 2026-06-03 | VALIDATION | ruff check + pyright executados, 3 list_all() consumers corrigidos |

