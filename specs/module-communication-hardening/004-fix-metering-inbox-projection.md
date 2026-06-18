# 004 — Corrigir projeção idempotente do Metering

**Status:** pending  
**Tipo:** metering  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 003

## Objetivo

Contabilizar requests, tokens, custo e Tool calls exatamente uma vez.

## Problemas observados

- Alguns handlers apenas registram log.
- `requested` e `started` podem contar a mesma requisição duas vezes.
- Payloads ausentes viram IDs sentinela.
- Replay precisa preservar totais.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Definir evento exato por métrica.
- Remover dupla contagem.
- Validar payload por tipo/version.
- Processar efeito e Inbox `processed` atomicamente.
- Implementar idempotência do efeito e testes de replay/concorrência.

## Alterações proibidas

- Persistir `UUID(int=0)`.
- Inferir project_id de agent_id.
- Marcar Inbox processada com payload obrigatório ausente.

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

1. Formalizar evento → métrica.
2. Criar validators.
3. Mover handlers para application use cases.
4. Garantir atomicidade.
5. Testar redelivery e concorrência.

## Testes obrigatórios

```bash
pytest tests/integration/metering -q
pytest tests/contract/events -q
```

## Critérios de aceitação

- Uma execução gera uma contagem de request.
- Tokens/custo/Tool calls correspondem aos eventos.
- Replay não altera totais.
- Nenhum ID sentinela é persistido.

## Rollback

Pausar consumer e reprocessar Inbox; não reativar recorder direto.
