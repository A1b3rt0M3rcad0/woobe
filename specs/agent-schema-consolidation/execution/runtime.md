# Runtime — Agent Schema Consolidation

## Branch de execução

`development_agent-schema-consolidation`

## Baseline

- source branch: `development`
- source SHA observado: `537e401356f956e928d1a7d025a3d9ccff2222aa`
- expected migration mode: `append_only`

## Guard obrigatório

```bash
test "$(git branch --show-current)" = "development_agent-schema-consolidation"
git merge-base --is-ancestor 537e401356f956e928d1a7d025a3d9ccff2222aa HEAD
git status --short
git rev-parse HEAD
```

## Decisões absolutas

- `agent` é o único schema do bounded context agent.
- `ai`, `knowledge` e `runtime` não existem no catálogo final.
- FK intra-agent é permitida.
- FK cross-module é proibida em qualquer direção.
- IDs externos são UUIDs opacos, indexados localmente.
- migrations são append-only por padrão.
- legacy views são temporárias e precisam ser removidas.
- `DROP SCHEMA ... CASCADE` é proibido no upgrade de contract.

## Estado atual

`pending`

## Status das specs

| Spec | Status | Data | SHA | Evidências | Próxima |
|---|---|---|---|---|---|
| 000 | pending | - | - | - | 001 |
| 001 | pending | - | - | - | 002 |
| 002 | pending | - | - | - | 003 |
| 003 | pending | - | - | - | 004 |
| 004 | pending | - | - | - | 005 |
| 005 | pending | - | - | - | 006 |
| 006 | pending | - | - | - | 007 |
| 007 | pending | - | - | - | 008 |
| 008 | pending | - | - | - | 009 |
| 009 | pending | - | - | - | 010 |
| 010 | pending | - | - | - | 011 |
| 011 | pending | - | - | - | 012 |
| 012 | pending | - | - | - | 013 |
| 013 | pending | - | - | - | 014 |
| 014 | pending | - | - | - | 015 |
| 015 | pending | - | - | - | 016 |
| 016 | pending | - | - | - | 017 |
| 017 | pending | - | - | - | - |

## Inventários obrigatórios

- `execution/inventory/current-database.md`
- `execution/inventory/objects.md`
- `execution/inventory/foreign-keys.md`
- `execution/inventory/table-map.md`
- `execution/inventory/migration-history.md`
- `execution/inventory/messaging-state.md`
- `execution/inventory/data-parity.md`
- `execution/inventory/deployment-observation.md`
- `execution/final-report.md`

## Riscos ativos iniciais

- estado real do banco ainda não inventariado;
- possíveis eventos pendentes em tabelas legacy;
- locks e volume de dados desconhecidos;
- dependências externas por FK, view, function ou raw SQL desconhecidas;
- migrations históricas criam schemas legados.

## Próxima spec recomendada

`000`

## Histórico de execução

Nenhuma spec executada.
