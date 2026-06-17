# 001 — Corrigir async/await e fronteiras transacionais do Agent

**Status:** pending  
**Tipo:** agent/application  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 000

## Objetivo

Tornar ask síncrono e streaming executáveis e atomicamente consistentes com a Outbox.

## Problemas observados

- `outbox.write` é chamado sem `await`.
- `_do_save_assistant_message` é usado sem `await`.
- Existem caminhos que retornam sucesso sem evento persistido.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Corrigir todos os awaits.
- Separar prepare, chamada externa e finalize/fail em UoWs curtos.
- Commitar mensagem e Outbox na mesma transação.
- Não ocultar falha de persistência final.
- Remover `except Exception: pass` em mudanças de estado críticas.

## Alterações proibidas

- Tornar writers síncronos para mascarar o defeito.
- Abrir transação durante LLM/stream/HTTP.
- Retornar sucesso quando a Outbox falhar.

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

1. Mapear coroutines do fluxo.
2. Corrigir awaits e tipos de retorno.
3. Isolar fases transacionais.
4. Tornar `_fail` determinístico.
5. Testar rollback e cancelamento do stream.

## Testes obrigatórios

```bash
pytest tests/integration/agent/test_ask_execution_phases.py -q
pytest tests/integration/agent/test_spec009_stream_job_orchestrator.py -q
python -W error::RuntimeWarning -m pytest tests/integration/agent -q
```

## Critérios de aceitação

- Zero coroutine não aguardada.
- Toda conclusão possui `completed.v1`; toda falha possui `failed.v1`.
- Mensagem e Outbox são atômicas.
- Nenhuma chamada externa ocorre com transação aberta.

## Rollback

Reverter os use cases sem reativar writes cross-module.
