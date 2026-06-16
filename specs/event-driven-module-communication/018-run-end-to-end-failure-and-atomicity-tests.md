# 018 — E2E de atomicidade, falhas, ordering e replay

**Status:** pending  
**Tipo:** testing  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Provar o fluxo completo sob crash windows e entregas duplicadas.

## Situação observada

Testes unitários não provam ACK ordering, publish/commit windows, duplicates, out-of-order e recovery.

## Pré-condições

- specs 006–017 concluídas

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
find tests -type f | sort
docker compose config || true
alembic current
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- tests/e2e/**
- tests/integration/messaging/**
- docker-compose.test.yml
- scripts/test/**

## Alterações proibidas

- network pública
- sleep longo sem polling
- ignorar dead events

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

1. Subir Postgres e RabbitMQ reais.
2. Executar ask sync/stream/job.
3. Provar agent state+Outbox.
4. Provar Inbox-before-ACK.
5. Provar efeito consumidor+processed.
6. Injetar crash antes/depois de publish, Inbox commit e handler commit.
7. Testar duplicate/out-of-order/retry/DLQ/replay.
8. Comparar paridade dos três modos.

## Testes obrigatórios

- happy path
- producer rollback
- duplicate
- consumer crash
- poison
- out-of-order
- replay
- broker outage

## Validação

```bash
pytest tests/integration/messaging -q
pytest tests/e2e -q
```

## Critérios de aceitação

- zero evento perdido
- zero efeito duplicado
- recovery automático
- paridade sync/stream/job

## Rollback

- falha bloqueia cutover
