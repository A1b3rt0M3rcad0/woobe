# 009 — Executar cutover com zero violação

**Status:** pending  
**Tipo:** cutover/e2e  
**Branch:** `development_module-communication-hardening`  
**Baseline de remediação:** `b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`  
**Dependências:** 000–008

## Objetivo

Validar a arquitetura integralmente e só então concluir a suíte.

## Problemas observados

- Cutover anterior terminou com falhas conhecidas e sem CI no HEAD.
- Relatório e código divergiam.

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_module-communication-hardening"
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message" src tests
rg -n "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created" src tests
```

Persistir evidências em `specs/module-communication-hardening/execution/inventory/`.

## Alterações requeridas

- Executar migrations do zero e upgrade de banco existente.
- Executar suíte completa, scans e E2E com RabbitMQ.
- Testar ask, stream e job.
- Validar eventual consistency de metering/observability.
- Configurar CI obrigatório.
- Atualizar runtime/final report com resultados reais.

## Alterações proibidas

- Aceitar testes vermelhos como preexistentes.
- Excluir testes para obter verde.
- Manter allowlist arquitetural.
- Declarar pronto sem broker/database E2E.

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

1. Subir stack limpa.
2. Aplicar migrations.
3. Executar full suite e fault injection.
4. Verificar invariantes no banco.
5. Validar CI.
6. Fazer rollback drill.
7. Concluir somente com zero violação.

## Testes obrigatórios

```bash
ruff check src tests
python -m compileall -q src
alembic upgrade head
pytest -q
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#" src tests
```

## Critérios de aceitação

- Ruff, compileall, migrations e full pytest passam.
- Zero import/write cross-module.
- Zero self-subscription sem caso de uso.
- Ask/stream/job produzem os mesmos contratos.
- Metering/observability convergem após replay.
- CI do HEAD está verde.

## Rollback

Pausar consumers, preservar mensagens, reverter deployment e reconciliar por event/message ID.
