# MANIFEST — Tools to Agent Consolidation

- Repository: `A1b3rt0M3rcad0/ProjectRAI`
- Baseline: `development` @ `209cf8147f87a2e9949fec33a34429ab70f166b5`
- Execution branch: `development_tools-to-agent-consolidation`
- Numbered specs: 18

## Ordem

1. `000-adr-incorporate-tools-into-agent.md` — ADR — incorporar tools ao bounded context agent
2. `001-inventory-tools-dependencies-and-public-contracts.md` — Inventariar tools, dependências e contratos públicos
3. `002-define-target-architecture-and-current-to-target-map.md` — Definir arquitetura-alvo e mapa current-to-target
4. `003-define-incremental-compatibility-and-rollback-protocol.md` — Definir protocolo incremental, compatibilidade e rollback
5. `004-add-baseline-characterization-and-architecture-guards.md` — Adicionar guards e testes de caracterização antes da migração
6. `005-move-tools-domain-contracts-into-agent.md` — Mover contratos de domínio de tools para agent
7. `006-move-tools-dtos-and-use-cases-into-agent.md` — Mover DTOs e casos de uso para application de agent
8. `007-consolidate-tool-execution-and-secure-secret-resolution.md` — Consolidar execução de ferramentas e resolução segura de segredos
9. `008-integrate-models-repositories-and-agent-unit-of-work.md` — Integrar models, mappers, repositories e AgentUnitOfWork
10. `009-move-presentation-and-preserve-http-api.md` — Mover controllers, composers, schemas e rotas preservando API
11. `010-consolidate-events-outbox-inbox-workers-and-registry.md` — Consolidar eventos, Outbox, Inbox, workers e registry
12. `011-migrate-tools-business-tables-to-agent-schema.md` — Migrar tabelas tools e secrets para schema agent
13. `012-consolidate-tools-legacy-outbox-and-inbox.md` — Consolidar Outbox e Inbox legadas de tools
14. `013-update-imports-bootstrap-alembic-and-dependency-injection.md` — Atualizar imports, bootstrap, Alembic e dependency injection
15. `014-execute-cutover-with-observability-and-temporary-shims.md` — Executar cutover com shims temporários e observabilidade
16. `015-add-security-transaction-and-concurrency-test-suite.md` — Adicionar suíte completa de segurança, transação e concorrência
17. `016-remove-legacy-tools-module-views-and-schema.md` — Remover módulo, shims, views e schema tools
18. `017-final-validation-and-consolidation-report.md` — Validação final e relatório de consolidação

## Política

- Ordem estrita.
- Specs 011, 012 e 016 exigem go/no-go.
- Falha de validação bloqueia dependentes.
- Runtime update é obrigatório.