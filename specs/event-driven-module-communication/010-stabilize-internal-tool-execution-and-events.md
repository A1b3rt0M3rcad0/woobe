# 010 — Tool interna: composição, secrets e eventos

**Status:** pending  
**Tipo:** agent  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Manter execução síncrona interna de Tool, corrigir wiring e emitir fatos externos pela Outbox.

## Situação observada

Tool já pertence ao agent. Porém o adapter instancia use case internamente, o runtime não injeta secret resolver de forma consistente, há assinaturas de composers divergentes e o agent consome seus próprios eventos Tool em handlers no-op.

## Pré-condições

- spec 009 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
sed -n '120,190p' src/modules/agent/infra/adapters/tool_executor.py
sed -n '1,180p' src/modules/agent/application/composers/tools_composers.py
sed -n '130,250p' src/modules/agent/application/use_cases/tools_use_cases.py
sed -n '1,130p' src/modules/agent/infra/messaging/inbox_handlers.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/agent/application/**
- src/modules/agent/infra/adapters/**
- src/modules/agent/infra/messaging/**
- tests/unit/agent/**

## Alterações proibidas

- RabbitMQ request/reply interno
- self-consumption
- expor secrets/output sensível

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

1. Injetar serviço de Tool no orchestrator.
2. Usar secret resolver em sync/stream/job.
3. Corrigir assinaturas e ordem de composers.
4. Emitir tool execution completed/failed no finalize.
5. Remover handlers que consomem eventos próprios.
6. Aplicar redaction/payload_ref.

## Testes obrigatórios

- tool result imediato
- secret resolution
- composer construction
- redaction
- no self-loop

## Validação

```bash
ruff check src/modules/agent
pytest tests/unit/agent tests/integration/agent -q
```

## Critérios de aceitação

- Tool continua interna
- fatos saem pela Outbox
- secrets resolvidos corretamente
- zero self-loop

## Rollback

- restaurar wiring interno anterior sem recriar módulo tools
