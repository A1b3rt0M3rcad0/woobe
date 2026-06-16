# ProjectRAI OpenCode Skills

Este pacote contém skills customizadas para executar a migração arquitetural do ProjectRAI de `ai`, `knowledge` e `runtime` para o bounded context `agent`.

Instalação sugerida no projeto:

```bash
mkdir -p .opencode
cp -R skills .opencode/
```

OpenCode espera diretórios no formato:

```text
.opencode/skills/<nome-da-skill>/SKILL.md
```

Skills incluídas:

- `projectrai-spec-orchestrator`: controla ordem das specs e atualização do runtime.
- `projectrai-discovery-inventory`: cria inventários obrigatórios antes de refatorar.
- `projectrai-architecture-boundaries`: impõe modular monolith, imports, shared, workers, UoW e FK boundaries.
- `projectrai-agent-migration`: orienta migração de `ai`, `knowledge` e `runtime` para `agent`.
- `projectrai-outbox-inbox`: orienta Outbox/Inbox, RabbitMQ, workers, retries, idempotência e locking.
- `projectrai-database-migrations`: orienta SQLAlchemy/Alembic, ownership, expand-migrate-contract e FKs.
- `projectrai-test-validation`: orienta testes, cleanup, validação final e relatório.
