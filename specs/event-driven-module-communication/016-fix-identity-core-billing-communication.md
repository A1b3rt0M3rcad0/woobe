# 016 — Identity, Core e Billing: remover integração de fachada

**Status:** pending  
**Tipo:** cross-module-audit  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Remover self-subscriptions e handlers no-op, mantendo consumers apenas para fluxos externos reais.

## Situação observada

Os três registram pipelines, mas filas usam o próprio prefixo e routers apenas escolhem um nome e escrevem log.

## Pré-condições

- spec 015 concluída
- matriz alvo revisada

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
rg -n "(IDENTITY|CORE|BILLING)_INBOX_ROUTING_KEYS|HANDLED_EVENTS" src/modules/{identity,core,billing}
rg -n "Routing event" src/modules/{identity,core,billing}/infra/messaging
rg -n "event_type=" src/modules/{identity,core,billing}/application
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/identity/**
- src/modules/core/**
- src/modules/billing/**
- tests/integration/**

## Alterações proibidas

- inventar side effect
- handler no-op
- evento próprio como comunicação interna

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

1. Versionar/prefixar eventos produzidos.
2. Remover bindings ao próprio namespace.
3. Implementar handler→use case→UoW somente para integrações externas comprovadas.
4. Não registrar consumer quando não houver subscription.
5. Manter outbox dispatchers produtores.
6. Documentar extension points sem código vazio.

## Testes obrigatórios

- event naming
- no self-binding
- no no-op
- outbox atomicity
- consumer registration

## Validação

```bash
ruff check src/modules/identity src/modules/core src/modules/billing
pytest tests/unit/identity tests/unit/core tests/unit/billing -q
pytest tests/integration/identity tests/integration/core tests/integration/billing -q
```

## Critérios de aceitação

- zero router fachada
- zero self-consumption
- eventos canônicos
- consumers reais

## Rollback

- restaurar binding somente em compatibilidade temporária
