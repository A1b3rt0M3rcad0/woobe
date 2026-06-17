# 004 — Envelope canônico de IntegrationEvent

**Status:** pending  
**Tipo:** messaging  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Unificar contrato, serialização, versionamento, correlação e idempotência de todos os módulos.

## Situação observada

O agent possui envelope rico; outros módulos publicam envelope reduzido. O writer de agent descarta routing/idempotência de eventos de domínio.

## Pré-condições

- spec 003 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
find src/modules -path '*/infra/messaging/event_mappers.py' -type f -print
sed -n '1,220p' src/modules/agent/infra/messaging/event_mappers.py
sed -n '1210,1250p' src/modules/agent/infra/database/repositories.py
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/shared/messaging/**
- src/modules/*/domain/events.py
- tests/unit/shared/**
- tests/contract/events/**

## Alterações proibidas

- regra de domínio em shared
- quebra sem compatibilidade
- payload sem schema/version

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

1. Criar IntegrationEvent imutável com event_id/type/version/producer/routing/occurred/payload/metadata/idempotency/correlation/causation.
2. Usar event_id como message_id.
3. Validar naming/versioning.
4. Definir idempotency determinística com occurrence discriminator.
5. Criar serializer/deserializer único.
6. Manter adapter legado temporário na borda.

## Testes obrigatórios

- round trip
- evento inválido
- idempotência
- compatibilidade de versão
- redaction

## Validação

```bash
ruff check src/shared/messaging tests/unit/shared tests/contract/events
pytest tests/unit/shared tests/contract/events -q
```

## Critérios de aceitação

- um envelope canônico
- routing preservado
- producer rastreável
- evento inválido rejeitado

## Rollback

- manter mappers antigos atrás de adapter até cutover
