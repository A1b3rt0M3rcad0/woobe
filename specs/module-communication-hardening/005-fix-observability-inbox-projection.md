# 005 — Corrigir projeção idempotente do Observability

**Status:** pending  
**Tipo:** observability  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 003

## Objetivo

Materializar traces consistentes com ordering, retries e estados terminais.

## Problemas observados

- Projeção dependia de eventos ausentes.
- Pode criar trace com IDs sentinela.
- Eventos fora de ordem e replay podem duplicar TraceEvents ou regredir estado.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Validar campos obrigatórios.
- Upsert idempotente de Trace.
- Persistir `source_event_id` único ou ID determinístico do TraceEvent.
- Tratar eventos fora de ordem.
- Impedir regressão de estado terminal.
- Atualizar efeito e Inbox atomicamente.

## Alterações proibidas

- Criar trace com `UUID(int=0)`.
- Usar horário de processamento como identidade.
- Consultar tabelas do Agent para completar payload.

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

1. Definir reducer do trace.
2. Criar validação.
3. Implementar upsert e vínculo ao evento de origem.
4. Testar ordering, replay, fallback e falha.

## Testes obrigatórios

```bash
pytest tests/integration/observability -q
pytest tests/contract/events -q
```

## Critérios de aceitação

- Replay não duplica TraceEvent.
- Estado terminal não regride.
- Nenhum ID sentinela.
- Zero leitura cross-module.

## Rollback

Pausar consumer e reconstruir projeções por replay.
