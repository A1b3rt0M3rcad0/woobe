# 007 — Outbox e catálogo de eventos do agent

**Status:** pending  
**Tipo:** agent-messaging  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Fazer o agent gravar eventos completos na mesma transação do estado local.

## Situação observada

O writer hardcodeia `agent.event` e reconstrói a idempotency key, ignorando campos dos eventos de domínio.

## Pré-condições

- specs 004–006 concluídas

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
rg -n "SQLAlchemyAgentOutboxEventWriter|routing_key="agent.event"|runtime\.ask\.|Agent.*V1" src/modules/agent
rg -n "_outbox\.write\(" src/modules/agent
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/agent/domain/events.py
- src/modules/agent/application/**
- src/modules/agent/infra/database/repositories.py
- tests/unit/agent/**

## Alterações proibidas

- publish direto no broker
- evento após commit
- payload sensível

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

1. Writer passa a aceitar IntegrationEvent completo.
2. Preservar event_id/routing/version/idempotency/correlation/causation.
3. Definir catálogo `agent.execution.*.v1` e `agent.tool.execution.*.v1`.
4. Deprecar `runtime.*` e eventos não versionados com compatibilidade.
5. Adicionar occurrence ids.
6. Provar state + Outbox atomicidade.

## Testes obrigatórios

- field preservation
- rollback
- multiple occurrences
- legacy compatibility
- redaction

## Validação

```bash
ruff check src/modules/agent tests/unit/agent
pytest tests/unit/agent tests/contract/events -q
```

## Critérios de aceitação

- zero `agent.event`
- eventos completos na Outbox
- rollback remove estado e evento

## Rollback

- adapter temporário para writer antigo
