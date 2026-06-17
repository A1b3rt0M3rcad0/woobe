# 008 — Endurecer RabbitMQ, DLQ, ACK, retry e replay

**Status:** pending  
**Tipo:** messaging/runtime  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 004, 005, 007

## Objetivo

Garantir entrega at-least-once operacional e tratamento correto de duplicatas e mensagens não roteáveis.

## Problemas observados

- DLQ é declarada, mas não vinculada ao DLX.
- Publisher não define `message_id` consistentemente.
- Tratamento de IntegrityError pode invalidar a transação externa.
- Falha unroutable pode ser interpretada como publish bem-sucedido.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Vincular DLQ ao DLX.
- Ativar publisher confirms e mandatory/unroutable handling.
- Publicar `message_id = event_id` e headers canônicos.
- Usar savepoint ou insert idempotente para duplicatas.
- Definir retry/poison policy.
- Testar replay e shutdown gracioso.

## Alterações proibidas

- ACK antes do commit.
- Requeue infinito de payload inválido.
- Marcar Outbox publicada sem confirmação.
- Tratar unroutable como sucesso.

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

1. Corrigir topologia.
2. Ativar confirms.
3. Completar metadata AMQP.
4. Corrigir duplicate handling.
5. Executar testes com broker real.

## Testes obrigatórios

```bash
pytest tests/integration/messaging -q
pytest tests/integration/workers -q
pytest tests/integration/metering/test_spec015_metering_retry_dlq.py -q
```

## Critérios de aceitação

- Rejeição permanente chega à DLQ.
- Unroutable não marca Outbox publicada.
- Duplicata recebe ACK sem duplicar efeito.
- Restart converge sem perda.

## Rollback

Pausar consumers/publishers preservando Outbox, Inbox e filas.
