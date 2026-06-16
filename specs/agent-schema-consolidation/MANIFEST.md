# Manifest — Agent Schema Consolidation

Branch: `development_agent-schema-consolidation`  
Baseline: `development` @ `537e401356f956e928d1a7d025a3d9ccff2222aa`

## Ordem

| Spec | Arquivo | Dependências |
|---|---|---|
| 000 | `000-architecture-decision-agent-schema-as-single-owner.md` | - |
| 001 | `001-inventory-current-database-and-migration-state.md` | 000 |
| 002 | `002-define-target-table-and-constraint-map.md` | 001 |
| 003 | `003-define-expand-migrate-contract-and-rollback-protocol.md` | 002 |
| 004 | `004-add-temporary-schema-and-foreign-key-architecture-guards.md` | 003 |
| 005 | `005-prepare-agent-schema-and-migration-preflight.md` | 004 |
| 006 | `006-move-ai-business-tables-to-agent-schema.md` | 005 |
| 007 | `007-move-knowledge-business-tables-to-agent-schema.md` | 006 |
| 008 | `008-move-runtime-business-tables-to-agent-schema.md` | 007 |
| 009 | `009-update-agent-sqlalchemy-models-and-internal-foreign-keys.md` | 008 |
| 010 | `010-remove-cross-module-foreign-keys-and-add-logical-id-indexes.md` | 009 |
| 011 | `011-consolidate-legacy-ai-knowledge-runtime-messaging-state.md` | 010 |
| 012 | `012-remove-runtime-code-references-to-legacy-schemas.md` | 011 |
| 013 | `013-update-alembic-head-and-fresh-install-contract.md` | 012 |
| 014 | `014-add-data-integrity-and-schema-migration-tests.md` | 013 |
| 015 | `015-execute-application-cutover-and-observability-window.md` | 014 |
| 016 | `016-drop-legacy-views-tables-and-schemas.md` | 015 |
| 017 | `017-final-validation-remove-allowlists-and-report.md` | 016 |

## Gate final

A suite somente pode ser marcada como concluída quando a spec 017 comprovar: schemas legados inexistentes, zero FKs cross-module, paridade de dados, migrations fresh/incremental equivalentes e regressão completa aprovada.
