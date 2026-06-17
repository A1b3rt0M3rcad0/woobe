# 008 — Execução síncrona do agent em fases transacionais

**Status:** pending  
**Tipo:** agent  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Remover writes diretos em metering/observability e evitar transação aberta durante LLM/HTTP.

## Situação observada

AskAgentUseCase recebe recorders que escrevem em módulos externos usando AgentUnitOfWork. TransactionalHandler mantém a transação durante toda a execução.

## Pré-condições

- spec 007 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '1,380p' src/modules/agent/application/use_cases/ask_use_case.py
sed -n '1,120p' src/modules/agent/application/composers/ask_agent_composer.py
sed -n '1,80p' src/shared/infra/transactional_handler.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/agent/application/**
- src/modules/agent/presentation/**
- tests/integration/agent/**

## Alterações proibidas

- importar metering/observability
- transação durante LLM/HTTP
- quebrar HTTP

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

1. Gerar execution_id/trace_id no agent.
2. Fase prepare curta: validar/persistir estado inicial + started Outbox.
3. Executar LLM/Tool fora de transação.
4. Fase finalize curta: resposta + eventos llm/tool/completed.
5. Fase failure curta: estado + failed Outbox.
6. Remover UsageRecorder/TraceRecorder cross-module.
7. Preservar response trace_id.

## Testes obrigatórios

- no open DB during external call
- prepare/finalize atomicity
- failure event
- HTTP compatibility

## Validação

```bash
ruff check src/modules/agent
pytest tests/unit/agent tests/integration/agent tests/contract -q
```

## Critérios de aceitação

- zero write cross-module
- eventos lifecycle na Outbox
- transações curtas
- trace_id imediato

## Rollback

- feature flag para use case legado durante janela
