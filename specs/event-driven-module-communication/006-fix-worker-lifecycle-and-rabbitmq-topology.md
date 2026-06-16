# 006 — Lifecycle de workers e topologia RabbitMQ

**Status:** pending  
**Tipo:** infrastructure  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Fazer consumers long-lived e pollers iniciarem, pararem e serem supervisionados corretamente.

## Situação observada

O startup apenas constrói o WorkerRunner e o guarda em app.state; `run_loop` não é iniciado. Reexecutar `consume()` em polling registraria callbacks duplicados.

## Pré-condições

- spec 005 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '107,145p' src/main.py
sed -n '1,180p' src/shared/workers/runner.py
sed -n '1,120p' src/shared/infra/rabbitmq.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/shared/workers/**
- src/shared/infra/rabbitmq.py
- src/main.py
- tests/integration/workers/**

## Alterações proibidas

- consumer novo por tick
- sys.exit no lifecycle FastAPI
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

1. Separar workers long-lived de pollers.
2. Criar start/stop e tarefas asyncio supervisionadas.
3. Iniciar no startup e cancelar/await no shutdown.
4. Declarar exchange/queues/bindings/DLX idempotentemente.
5. Expor health por worker.
6. Impedir callback duplicado.

## Testes obrigatórios

- startup/shutdown
- single consumer
- failure isolation
- RabbitMQ unavailable

## Validação

```bash
ruff check src/shared/workers src/shared/infra/rabbitmq.py src/main.py
pytest tests/integration/workers -q
```

## Critérios de aceitação

- workers realmente executam
- um consumer por queue
- shutdown limpo
- falha isolada

## Rollback

- feature flag para bootstrap anterior
- cancelar tarefas antes de reverter
