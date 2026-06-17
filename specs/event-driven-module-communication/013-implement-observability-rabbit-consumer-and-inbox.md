# 013 — Consumer RabbitMQ e Inbox do observability

**Status:** pending  
**Tipo:** observability  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Implementar broker consumer que persiste lifecycle do agent na Inbox.

## Situação observada

O registry é vazio e o worker atual apenas consulta tabela local; o agent contorna isso escrevendo traces diretamente.

## Pré-condições

- spec 010 concluída
- subscription matrix aprovada

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,120p' src/modules/observability/infra/workers/registry.py
sed -n '1,160p' src/modules/observability/infra/workers/inbox_consumer.py
sed -n '1,120p' src/modules/observability/infra/messaging/inbox_handlers.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/observability/infra/**
- tests/integration/observability/**

## Alterações proibidas

- binding `observability.#`
- persistir trace no callback
- ACK prematuro

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

1. Declarar `observability.inbox`.
2. Vincular agent.execution.* e tool facts.
3. Validar/persistir Inbox canônica.
4. ACK/NACK/reject conforme transação.
5. Separar consumer e processor.

## Testes obrigatórios

- broker→Inbox
- duplicates
- invalid/DLQ
- DB failure
- binding matrix

## Validação

```bash
ruff check src/modules/observability
pytest tests/integration/observability tests/integration/messaging -q
```

## Critérios de aceitação

- eventos chegam à Inbox
- ACK após commit
- callback não grava trace

## Rollback

- desregistrar consumer e preservar Inbox
