# 009 — Streaming e AskJobs no mesmo orchestrator

**Status:** pending  
**Tipo:** agent  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Aplicar o lifecycle prepare/external/finalize/fail ao SSE e aos jobs.

## Situação observada

O stream cria recorders com sessões que fecha e depois reutiliza objetos; AskJobWorker usa os mesmos adapters e não está registrado. CreateAskJob não grava Outbox.

## Pré-condições

- spec 008 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,520p' src/modules/agent/application/use_cases/ask_agent_stream_service.py
sed -n '1,180p' src/modules/agent/infra/workers/ask_job_worker.py
sed -n '1,120p' src/modules/agent/infra/workers/registry.py
sed -n '180,230p' src/modules/agent/application/use_cases/runtime_use_cases.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/agent/application/**
- src/modules/agent/infra/workers/**
- tests/**

## Alterações proibidas

- repository após sessão fechada
- duplicar event model
- cross-module UoW

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

1. Extrair orchestrator compartilhado.
2. Aplicar fases curtas ao stream.
3. Criar job + requested Outbox atomicamente.
4. Registrar AskJobWorker como poller interno.
5. Remover imports dinâmicos de recorders.
6. Preservar SSE e polling contracts.

## Testes obrigatórios

- SSE success/failure/disconnect
- job concurrency
- job+outbox
- worker registration
- no closed session

## Validação

```bash
ruff check src/modules/agent
pytest tests/unit/agent tests/integration/agent tests/contract -q
```

## Critérios de aceitação

- sync/stream/job emitem os mesmos fatos
- AskJobWorker executa
- zero adapter cross-module

## Rollback

- desativar novo orchestrator por flag sem reverter eventos
