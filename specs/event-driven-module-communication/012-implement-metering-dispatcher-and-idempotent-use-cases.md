# 012 — Dispatcher e casos de uso idempotentes do metering

**Status:** pending  
**Tipo:** metering  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Transformar eventos do agent em UsageEvents/agregados na transação do metering.

## Situação observada

RecordUsageUseCase existe, mas o fluxo Inbox não o chama e não há atomicidade entre efeito, nova Outbox e Inbox processed.

## Pré-condições

- spec 011 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,180p' src/modules/metering/application/use_cases/metering_use_cases.py
sed -n '1,180p' src/modules/metering/infra/database/unit_of_work.py
sed -n '1,180p' src/modules/metering/infra/workers/inbox_processor.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/metering/application/**
- src/modules/metering/infra/**
- tests/integration/metering/**

## Alterações proibidas

- AgentRepository
- consulta ao schema agent
- processed fora da transação

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

1. Criar handlers por type/version.
2. Mapear llm_completed para tokens/cost.
3. Mapear tool execution para tool_calls.
4. Executar handler com MeteringUnitOfWork na mesma sessão do processor.
5. Persistir usage/agregados/nova Outbox/processed atomicamente.
6. Unknown→ignored.
7. Garantir source event id para deduplicação.

## Testes obrigatórios

- atomic effect
- rollback/retry
- no double count
- out-of-order
- unknown ignored

## Validação

```bash
ruff check src/modules/metering
pytest tests/unit/metering tests/integration/metering -q
```

## Critérios de aceitação

- zero double count
- zero import agent
- replay seguro
- atomicidade comprovada

## Rollback

- parar processor e preservar Inbox/usage com source id
