# Specs de Migração Arquitetural — ProjectRAI `agent`

Este pacote contém specs operacionais para migrar incrementalmente `ai`, `knowledge` e `runtime` para o bounded context `agent`, mantendo o ProjectRAI como modular monolith.

## Como executar

1. Comece por `/specs/execution/runtime.md`.
2. Execute as specs em ordem numérica, salvo bloqueio registrado no runtime.
3. Nunca mova arquivos físicos antes de concluir as specs de discovery 003-009 e os testes arquiteturais iniciais 015-019.
4. Para cada spec:
   - leia pré-condições;
   - execute comandos de detecção;
   - faça alterações permitidas;
   - rode testes obrigatórios;
   - rode comandos de validação confirmados no inventário;
   - atualize `/specs/execution/runtime.md`.
5. Shims temporários são permitidos apenas com depreciação explícita, teste de compatibilidade e spec de remoção.

## Ordem macro

1. ADR e regras: 000-002.
2. Discovery: 003-009.
3. Skeleton `agent`: 010-014.
4. Testes arquiteturais iniciais e allowlist: 015-019.
5. Migração por camada: 020-045.
6. Workers/shared runner: 050-063.
7. Agent Outbox/Inbox/UoW: 070-079.
8. Agent workers/RabbitMQ: 080-085.
9. Outros módulos consumidores: 090-094.
10. Padronização event-driven: 100-109.
11. Testes finais e comportamentais: 110-129.
12. Bootstrap/config/migrations: 130-134.
13. Depreciação/remoção legado: 140-145.
14. Limpeza e validação final: 150-154.

## Regras absolutas

- Não criar microservices.
- Não manter `ai`, `knowledge` e `runtime` como módulos independentes no estado final.
- Não permitir que módulo importe internals de outro módulo.
- Não permitir UoW cross-module.
- Não colocar regra de negócio em workers.
- Não colocar domínio em `shared`.
- Não remover legado antes de inventário, testes, shims e validações finais.

## Estado inicial usado para calibrar as specs

Estado preliminar observado no ProjectRAI em 2026-06-12:

- `src/main.py` registra diretamente os routers `modules.ai`, `modules.knowledge` e `modules.runtime`.
- `src/workers/runner.py` instancia `OutboxPublisherWorker`, `InboxConsumerWorker`, `InboxDispatcherWorker` e `AskJobWorker` diretamente.
- `src/workers/dispatcher.py` contém handlers por evento de negócio e conhece eventos de `identity`, `core`, `ai`, `knowledge` e `metering`.
- `src/shared/workers/outbox_publisher.py` e `src/shared/workers/inbox_dispatcher.py` mantêm listas fixas de módulos, incluindo `ai`, `knowledge` e `runtime`.
- `src/shared/workers/inbox_consumer.py` roteia eventos pelo primeiro segmento do `event_type`, usando uma queue global `projectrai.inbox` e import dinâmico de models do produtor.
- `src/modules/runtime/service/ask_use_case.py` importa diretamente domínio/repositórios de `ai`, `knowledge`, `metering` e `observability`.
- `src/modules/runtime/infra/ask_job_worker.py` monta um caso de uso com repositórios de `ai`, `knowledge`, `runtime`, `metering` e `observability` sob um UoW compartilhado.
- `src/modules/ai/infra/models.py`, `src/modules/knowledge/infra/models.py` e `src/modules/runtime/infra/models.py` têm schemas separados e Outbox/Inbox próprias.
- `migrations/env.py` importa explicitamente models de `ai`, `knowledge` e `runtime` para metadata do Alembic.

