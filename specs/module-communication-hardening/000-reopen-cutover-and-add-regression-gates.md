# 000 — Reabrir o cutover e criar gates de regressão

**Status:** pending  
**Tipo:** architecture/testing  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 019

## Objetivo

Corrigir o estado documental da suíte e tornar todos os bloqueadores reproduzíveis antes de alterar produção.

## Problemas observados

- 018/019 foram marcadas como concluídas com testes falhando.
- Guards aceitam violações conhecidas.
- Não há cobertura adequada para coroutine sem `await`, wiring de Tool, catálogo inconsistente e self-subscription.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Marcar o cutover atual como `remediation-required`.
- Criar matriz defeito → teste → spec corretiva.
- Adicionar testes de caracterização para ask, stream, job, Tool, subscriptions e idempotência.
- Remover semântica de allowlist aceitável dos guards finais.

## Alterações proibidas

- Corrigir código produtivo nesta spec.
- Reclassificar falhas como preexistentes sem evidência.
- Declarar sucesso sem saída e exit code registrados.

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

1. Reabrir 018/019 no runtime.
2. Criar `known-defects.md`.
3. Criar um teste por defeito confirmado.
4. Fixar baseline e escopo fechado.
5. Registrar os testes inicialmente vermelhos pelos motivos esperados.

## Testes obrigatórios

```bash
ruff check tests/architecture tests/integration/agent
pytest tests/architecture -q
pytest tests/integration/agent -q
```

## Critérios de aceitação

- Runtime não declara mais a suíte concluída.
- Cada defeito possui teste e owner.
- Nenhuma violação cross-module é aceita por allowlist ao final.

## Rollback

Reverter apenas testes/documentação desta spec.
