# 003 — Testes de caracterização e guards arquiteturais

**Status:** pending  
**Tipo:** testing  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Congelar contratos e impedir novas violações durante a migração.

## Situação observada

Imports dinâmicos, FKs e eventos não versionados podem escapar de testes simples. Sync, stream, jobs e Tool precisam de caracterização antes do refactor.

## Pré-condições

- spec 002 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
find tests -type f | sort
pytest --collect-only -q
rg -n "architecture|outbox|inbox|rabbit|metering|observability|ask_stream" tests
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- tests/architecture/**
- tests/contract/**
- tests/integration/messaging/**
- tests/unit/shared/**

## Alterações proibidas

- alterar comportamento produtivo
- allowlist aberta
- remover asserts existentes

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

1. Criar guard AST para imports estáticos e importlib.
2. Detectar repository externo com UoW/sessão estrangeira.
3. Detectar FK cross-module.
4. Detectar routing key genérica e evento sem versão.
5. Detectar self-subscription.
6. Caracterizar ask sync, SSE, job e Tool.
7. Criar allowlist temporária com contagem exata.

## Testes obrigatórios

- architecture imports
- database boundaries
- event contracts
- worker topology
- HTTP/SSE compatibility

## Validação

```bash
pytest tests/architecture -q
pytest tests/contract -q
pytest tests/integration/messaging -q
```

## Critérios de aceitação

- violações atuais capturadas
- novas violações falham CI
- contratos públicos congelados

## Rollback

- remover somente testes novos
