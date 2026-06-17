# 003 — Completar eventos do Agent e corrigir idempotência

**Status:** pending  
**Tipo:** messaging/domain  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 001, 002

## Objetivo

Alinhar eventos produzidos às subscriptions e garantir identidade única por ocorrência.

## Problemas observados

- Consumers esperam `started`, `llm_completed` e `tool_completed`, mas o Agent não os produz consistentemente.
- Idempotency keys colidem entre execuções da mesma sessão e atualizações repetidas da mesma Tool.
- Correlação/causação não é propagada pela execução.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Criar `execution_id` único.
- Implementar `started.v1`, `llm_completed.v1` e `tool_completed.v1`.
- Usar `execution_id`/`event_id` como discriminator por ocorrência.
- Propagar um `correlation_id` e cadeia de `causation_id`.
- Redigir payloads e atualizar catálogo/matriz.

## Alterações proibidas

- Remover unique constraint para tolerar colisão.
- Usar timestamp textual como identidade.
- Publicar prompts, secrets, headers ou outputs sensíveis.

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

1. Definir máquina de estados.
2. Criar classes/factories.
3. Emitir eventos nos pontos reais.
4. Corrigir idempotência.
5. Atualizar contratos e subscriptions.
6. Testar duas execuções na mesma sessão.

## Testes obrigatórios

```bash
pytest tests/unit/agent/test_agent_outbox_writer.py -q
pytest tests/contract/events -q
pytest tests/integration/agent -q
```

## Critérios de aceitação

- Eventos esperados são realmente produzidos.
- Duas execuções na mesma sessão não colidem.
- Event type/version/routing key coincidem.
- Correlação e causação são verificáveis.

## Rollback

Desativar novos bindings de forma coordenada; não reutilizar chaves colidentes.
