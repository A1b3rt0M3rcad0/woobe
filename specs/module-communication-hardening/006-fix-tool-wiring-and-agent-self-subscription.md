# 006 — Corrigir Tool e remover self-subscription do Agent

**Status:** pending  
**Tipo:** agent/tools/workers  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 001, 002, 003

## Objetivo

Manter Tool síncrona e interna, corretamente composta, removendo Agent Outbox → Agent Inbox sem caso de uso.

## Problemas observados

- Constructors e composers de Tool são incompatíveis.
- Ask síncrono pode não receber Tool executor.
- Stream reutiliza repository de UoW encerrado.
- Agent continua inscrito em `agent.#` com router vazio.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Corrigir composers por argumentos nomeados.
- Criar executor/factory válido por execução.
- Separar leitura/configuração da chamada HTTP externa.
- Emitir fatos de Tool pela Outbox.
- Remover Agent Inbox Consumer/Processor e binding `agent.#`.
- Atualizar guards e contagem de workers.

## Alterações proibidas

- Colocar RabbitMQ no request/reply da Tool.
- Manter self-subscription para consumir fatos próprios.
- Manter UoW aberto durante HTTP.

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

1. Corrigir assinaturas.
2. Definir factory por execução.
3. Corrigir lifecycle de repository/session.
4. Emitir eventos de Tool.
5. Remover workers/binding próprios.

## Testes obrigatórios

```bash
pytest tests/unit/agent/test_tools_application.py -q
pytest tests/unit/agent/test_spec010_tool_executor_and_handlers.py -q
pytest tests/integration/agent/test_tools_transaction.py -q
pytest tests/architecture/test_event_self_subscriptions.py -q
```

## Critérios de aceitação

- Endpoints de Tool não geram TypeError.
- Tool funciona em ask, stream e job.
- Nenhuma sessão fechada é reutilizada.
- Agent não consome `agent.#`.

## Rollback

Reverter factory mantendo Tool interna; não reativar self-subscription.
