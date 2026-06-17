# 011 — Consumer RabbitMQ e Inbox do metering

**Status:** pending  
**Tipo:** metering  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Implementar broker consumer que persiste Inbox antes do ACK.

## Situação observada

O registry de metering é vazio; o worker atual apenas consulta a tabela Inbox e o router não executa caso de uso.

## Pré-condições

- spec 010 concluída
- subscription matrix aprovada

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,120p' src/modules/metering/infra/workers/registry.py
sed -n '1,160p' src/modules/metering/infra/workers/inbox_consumer.py
sed -n '1,120p' src/modules/metering/infra/messaging/inbox_handlers.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/metering/infra/**
- tests/integration/metering/**

## Alterações proibidas

- ACK antes do commit
- binding `metering.#`
- regra de negócio no callback

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

1. Declarar `metering.inbox`.
2. Vincular somente fatos quantificáveis do agent.
3. Validar envelope e persistir Inbox deduplicada.
4. ACK após commit; NACK transient; invalid→DLQ.
5. Separar consumer broker e processor.

## Testes obrigatórios

- broker→Inbox
- duplicate
- DB failure
- invalid envelope
- binding exactness

## Validação

```bash
ruff check src/modules/metering
pytest tests/integration/metering tests/integration/messaging -q
```

## Critérios de aceitação

- mensagem chega uma vez à Inbox
- nenhuma regra antes do commit
- bindings corretos

## Rollback

- desregistrar consumer e preservar Inbox
