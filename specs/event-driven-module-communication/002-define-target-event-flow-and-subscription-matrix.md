# 002 — Matriz alvo de eventos, ownership e subscriptions

**Status:** pending  
**Tipo:** architecture  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Definir produtor, evento, consumidor, handler, efeito, idempotência e redaction de cada fluxo real.

## Situação observada

As filas atuais tendem a consumir o próprio prefixo. Metering e observability, que deveriam consumir fatos do agent, não registram workers funcionais.

## Pré-condições

- spec 001 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
cat specs/event-driven-module-communication/execution/inventory/event-catalog-current.md
rg -n "_INBOX_ROUTING_KEYS|register_.*_workers|HANDLED_EVENTS" src/modules
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- execution/inventory/event-flow-target.md
- execution/inventory/subscription-matrix.md
- execution/inventory/event-payload-policy.md
- execution/inventory/compatibility-map.md

## Alterações proibidas

- inventar side effect sem caso de uso
- evento com segredo
- self-binding sem justificativa

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

1. Definir agent como produtor do lifecycle de execução.
2. Definir metering como consumidor de fatos quantificáveis.
3. Definir observability como consumidor do lifecycle e etapas.
4. Definir eventos mínimos requested/started/llm_completed/tool_execution_completed/fallback/completed/failed.
5. Definir compatibilidade de eventos `runtime.*`, `tools.*` e não versionados.
6. Definir redaction e payload references.
7. Determinar subscriptions reais para identity/core/billing ou remover consumers sem uso.

## Testes obrigatórios

- matriz produtor→evento→consumidor→handler→efeito
- nenhum self-binding alvo

## Validação

```bash
test -s specs/event-driven-module-communication/execution/inventory/event-flow-target.md
test -s specs/event-driven-module-communication/execution/inventory/subscription-matrix.md
test -s specs/event-driven-module-communication/execution/inventory/event-payload-policy.md
```

## Critérios de aceitação

- metering e observability têm subscriptions concretas
- agent não consome eventos próprios de Tool
- demais consumers só existem com caso de uso

## Rollback

- reverter documentos antes da implementação
