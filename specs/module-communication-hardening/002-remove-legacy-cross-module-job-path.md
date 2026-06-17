# 002 — Remover o caminho legado cross-module do AskJob

**Status:** pending  
**Tipo:** agent/workers  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 001

## Objetivo

Fazer HTTP, stream e AskJob usarem o mesmo orquestrador event-driven.

## Problemas observados

- AskJob ainda instancia `MeteringUsageRecorder` e `ObservabilityTraceRecorder`.
- A injeção de repositories ativa `_legacy_mode`.
- O job compartilha UoW do Agent com repositories externos.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Migrar AskJob para o caminho phased.
- Remover `_legacy_mode`, `_execute_legacy` e parâmetros de compatibilidade.
- Excluir os dois recorders e ports exclusivos de escrita direta.
- Atualizar estado do job em transações curtas.
- Garantir os mesmos eventos de HTTP/stream.

## Alterações proibidas

- Manter adapters desativados no source tree.
- Usar feature flag para reativar escrita direta.
- Processar LLM dentro da transação de claim do job.

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

1. Criar composer/orquestrador único.
2. Migrar AskJobWorker.
3. Remover modo legado e adapters.
4. Atualizar guards.
5. Testar retry sem duplicação.

## Testes obrigatórios

```bash
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_execute_legacy|_legacy_mode" src tests
pytest tests/integration/agent/test_spec009_stream_job_orchestrator.py -q
pytest tests/architecture/test_event_dynamic_imports.py -q
```

## Critérios de aceitação

- Zero import/write Agent → Metering/Observability.
- AskJob usa o mesmo fluxo phased.
- Retry não duplica efeitos.

## Rollback

Reverter o novo composer sem reintroduzir os adapters.
