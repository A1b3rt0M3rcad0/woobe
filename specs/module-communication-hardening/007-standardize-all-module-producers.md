# 007 — Padronizar produtores Outbox de todos os módulos

**Status:** pending  
**Tipo:** messaging/modules  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 003–006

## Objetivo

Aplicar o contrato canônico a Billing, Core, Identity, Metering e Observability.

## Problemas observados

- Billing/Core ainda emitem eventos como `plan.created`, `customer.created` e `project.created`.
- Writers compartilhados não preenchem todos os campos canônicos.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Criar eventos versionados por módulo.
- Fazer writer receber `IntegrationEvent` ou todos os campos canônicos.
- Preencher event ID, producer, routing key, idempotency, correlation e causation.
- Migrar todos os call sites.
- Criar guard contra eventos não versionados.

## Alterações proibidas

- Manter defaults vazios para campos obrigatórios.
- Editar migrations anteriores.
- Criar compatibility map permanente e indefinido.

## Invariantes

- Cada bounded context grava apenas nas próprias tabelas e usa seu próprio Unit of Work.
- Comunicação cross-module: estado local + Outbox na mesma transação → dispatcher → RabbitMQ → Inbox persistida → ACK → processor → caso de uso local.
- ACK somente após commit da Inbox.
- Efeito local, eventual nova Outbox e Inbox `processed` na mesma transação.
- Nenhuma transação permanece aberta durante LLM, HTTP externo, streaming ou espera do broker.
- Tool permanece síncrona e interna ao módulo `agent`; fatos externos saem pela Outbox.
- Eventos seguem `<producer>.<capability>.<fact>.vN`.
- Nenhuma spec é concluída com testes obrigatórios falhando ou violações em allowlist.

## Plano de implementação

1. Inventariar todos os writers.
2. Definir catálogo por módulo.
3. Refatorar writer compartilhado.
4. Migrar producers e mappers.
5. Atualizar testes.

## Testes obrigatórios

```bash
pytest tests/architecture/test_event_versioning.py -q
pytest tests/contract/events -q
pytest tests/integration/billing tests/integration/core tests/integration/identity -q
```

## Critérios de aceitação

- Zero evento produtivo não versionado.
- Todos os records possuem campos canônicos.
- Routing key representa o evento real.
- Producers não dependem de defaults de banco para identidade.

## Rollback

Reverter producers por módulo sem quebrar schema canônico.
