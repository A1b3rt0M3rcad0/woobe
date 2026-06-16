# 014 — Projeção idempotente de observability

**Status:** pending  
**Tipo:** observability  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Criar/atualizar traces por eventos do agent, sem leitura síncrona do módulo produtor.

## Situação observada

Os casos de uso existem, mas routers não os executam. No target, o trace_id é criado pelo agent para resposta imediata e projeção eventual.

## Pré-condições

- spec 013 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,260p' src/modules/observability/application/use_cases/observability_use_cases.py
sed -n '1,180p' src/modules/observability/infra/database/unit_of_work.py
sed -n '1,180p' src/modules/observability/infra/workers/inbox_processor.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/observability/application/**
- src/modules/observability/infra/**
- tests/integration/observability/**

## Alterações proibidas

- buscar agent
- UUID aleatório ignorando trace_id
- payload sensível bruto

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

1. Upsert Trace por trace_id externo.
2. State machine started/completed/failed idempotente.
3. TraceEvents para LLM/Tool/fallback.
4. Suportar out-of-order com placeholder reconciliável.
5. Projeção+nova Outbox+processed atomicamente.
6. Redaction/payload_ref.

## Testes obrigatórios

- ordered/out-of-order
- duplicate
- failed
- redaction
- rollback

## Validação

```bash
ruff check src/modules/observability
pytest tests/unit/observability tests/integration/observability -q
```

## Critérios de aceitação

- trace_id preservado
- zero import agent
- projeção replay-safe
- consistência eventual explícita

## Rollback

- parar processor e reconstruir por replay
