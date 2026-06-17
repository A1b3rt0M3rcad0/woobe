# 005 — Persistência canônica de Outbox e Inbox

**Status:** pending  
**Tipo:** database  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Padronizar campos, índices, locks e estados sem compartilhar tabelas entre módulos.

## Situação observada

Os modelos abstratos usados por vários módulos não têm message_id, routing, idempotency e locks equivalentes ao agent.

## Pré-condições

- spec 004 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,240p' src/shared/infra/database/outbox.py
sed -n '1,240p' src/shared/infra/database/inbox.py
rg -n "class .*InboxEventModel|class .*OutboxEventModel" src/modules
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/shared/infra/database/**
- src/modules/*/infra/database/models.py
- migrations/versions/new_*
- tests/migrations/**

## Alterações proibidas

- tabela global compartilhada
- editar migration histórica
- remover eventos

## Regras invariantes

- Mudança de estado pertencente a outro bounded context nunca pode ocorrer por import direto, repository externo, model externo, sessão compartilhada ou Unit of Work estrangeiro.
- O fluxo obrigatório cross-module é: estado local + Outbox na mesma transação → dispatcher → RabbitMQ → consumer → Inbox persistida → ACK → processor/dispatcher → caso de uso consumidor → estado local + eventual nova Outbox + Inbox `processed` na mesma transação.
- O ACK do broker só ocorre após commit da Inbox.
- O processamento da Inbox, o efeito local, a nova Outbox e a marcação `processed` devem ser atômicos.
- Consumidores são idempotentes por `message_id` e `idempotency_key`.
- Eventos são contratos versionados no formato `<producer>.<capability>.<fact>.vN`.
- Routing keys representam o evento real; `agent.event` e equivalentes genéricos são proibidos.
- Queue bindings representam eventos externos realmente consumidos. Self-subscription exige justificativa explícita e, por padrão, é proibida.
- Handlers de Inbox devem chamar casos de uso reais. Router que apenas escreve log não é implementação.
- IDs de outro módulo são UUIDs opacos e indexados, sem Foreign Key física cross-module.
- Não manter transação aberta durante LLM, HTTP externo, streaming ou espera de broker.
- Payloads não transportam secrets, API keys, authorization headers, prompts completos, respostas completas ou tool outputs sensíveis sem redaction/reference explícita.
- Migrations são append-only. Não editar revisions aplicadas e não usar `DROP ... CASCADE`.
- Tool já pertence ao bounded context `agent`. A execução de Tool durante o loop do LLM continua síncrona e interna; fatos dessa execução destinados a outros módulos saem pela Outbox do `agent`.
- Toda spec concluída atualiza `execution/runtime.md` com comandos, exit codes, arquivos, decisões e riscos.

## Plano de implementação

1. Definir mixins canônicos sem ownership de tabela.
2. Adicionar routing/metadata/idempotency/message_id/locks.
3. Criar unique constraints e índices parciais.
4. Padronizar state machines.
5. Criar migration append-only com backfill determinístico.
6. Preservar tabelas por módulo.

## Testes obrigatórios

- fresh install
- upgrade baseline
- downgrade
- duplicate
- lock timeout
- transitions

## Validação

```bash
alembic upgrade head
pytest tests/migrations -q
alembic downgrade -1
alembic upgrade head
```

## Critérios de aceitação

- Inbox deduplica antes do ACK
- Outbox usa SKIP LOCKED
- nenhuma tabela global de mensageria

## Rollback

- downgrade sem apagar eventos novos
- export obrigatório antes de remoção
