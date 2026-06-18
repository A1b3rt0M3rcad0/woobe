# 015 — Registries, retries, DLQ, locks e replay

**Status:** pending  
**Tipo:** resilience  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Completar e operacionalizar os pipelines de metering e observability.

## Situação observada

Ambos têm publishers/dispatchers parciais, mas registries vazios. Há queries com cutoff de uma hora e divergências de métodos abstratos/estados.

## Pré-condições

- specs 011–014 concluídas

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,180p' src/modules/metering/infra/workers/outbox_dispatcher.py
sed -n '1,180p' src/modules/observability/infra/workers/outbox_dispatcher.py
rg -n "timedelta\(hours=1\)|mark_failed|mark_dead|mark_retryable" src/modules/*/infra/workers
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/metering/infra/workers/**
- src/modules/observability/infra/workers/**
- src/shared/workers/**
- scripts/messaging/**
- tests/integration/**

## Alterações proibidas

- retry infinito
- poison requeue
- estado fora da state machine

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

1. Registrar consumer/processor/outbox dispatcher.
2. Corrigir interfaces abstratas.
3. Usar available_at<=now, lock timeout e backoff com jitter.
4. Configurar DLQ/dead events.
5. Criar replay por ids/status/range.
6. Adicionar métricas lag/retries/dead/throughput.

## Testes obrigatórios

- registry
- retry schedule
- max attempts
- DLQ
- replay
- concurrency

## Validação

```bash
ruff check src/modules/metering src/modules/observability src/shared/workers
pytest tests/integration/metering tests/integration/observability tests/integration/workers -q
```

## Critérios de aceitação

- pipelines registrados
- sem atraso de uma hora
- replay idempotente
- dead observável

## Rollback

- desativar workers por config sem apagar dados
