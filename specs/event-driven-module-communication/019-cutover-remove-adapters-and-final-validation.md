# 019 — Cutover, remoção de adapters e validação final

**Status:** pending  
**Tipo:** cutover  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Ativar o caminho event-driven como único fluxo e produzir relatório auditável.

## Situação observada

Adapters cross-module, imports dinâmicos, self-handlers e allowlists só podem ser removidos após consumers e E2E verdes.

## Pré-condições

- spec 018 concluída
- rollback drill aprovado
- backlog conhecido

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|import_module\(\"modules\.(metering|observability)" src tests
rg -n "routing_key="agent.event"|_INBOX_ROUTING_KEYS.*\["(agent|identity|core|billing)\.#" src
git status --short
alembic current
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- remoção de adapters legados
- configuração final
- documentação
- execution/final-report.md
- execution/runtime.md

## Alterações proibidas

- concluir com backlog desconhecido
- apagar Inbox/Outbox
- ocultar compatibilidade residual

## Regras invariantes

- Mudança de estado pertencente a outro bounded context nunca pode ocorrer por import direto, repository externo, model externo, sessão compartilhada ou Unit of Work estrangeiro.
- O fluxo obrigatório cross-module é: estado local + Outbox na mesma transação → dispatcher → RabbitMQ → consumer → Inbox persistida → ACK → processor/dispatcher → caso de uso consumidor → estado local + eventual nova Outbox + Inbox `processed` na mesma transação.
- O ACK do broker só ocorre após commit da Inbox.
- O processamento da Inbox, o efeito local, a nova Outbox e a marcação `processed` devem ser atômicos.
- Consumidores são idempotentes por `message_id` e `idempotency_key`.
- Eventos são contratos versionados no formato `<producer>.<capability>.<fact>.vN`.
- Routing keys representam o evento real; `agent.event` e equivalentes genéricos são proibidos.
- Queue bindings representam eventos externos realmente consumidos. Self-subscription exige justificativa explícita e, por padrão, é proibida.
- Handlers de Inbox devem chamar casos de uso reais. Router que apenas escreve log não é implementação.
- IDs de outro módulo são UUIDs opacos e indexados, sem Foreign Key física cross-module.
- Não manter transação aberta durante LLM, HTTP externo, streaming ou espera de broker.
- Payloads não transportam secrets, API keys, authorization headers, prompts completos, respostas completas ou tool outputs sensíveis sem redaction/reference explícita.
- Migrations são append-only. Não editar revisions aplicadas e não usar `DROP ... CASCADE`.
- Tool já pertence ao bounded context `agent`. A execução de Tool durante o loop do LLM continua síncrona e interna; fatos dessa execução destinados a outros módulos saem pela Outbox do `agent`.
- Toda spec concluída atualiza `execution/runtime.md` com comandos, exit codes, arquivos, decisões e riscos.

## Plano de implementação

1. Ativar event-driven como único caminho.
2. Remover recorders/imports dinâmicos.
3. Remover self-handlers e allowlists.
4. Validar filas/bindings/health/backlog.
5. Executar suíte e scans.
6. Gerar relatório com migrations, eventos, SLOs, riscos e rollback.
7. Concluir somente com zero violação.

## Testes obrigatórios

- full suite
- architecture/db scan
- broker topology
- OpenAPI/SSE
- replay

## Validação

```bash
ruff check src tests
pytest -q
alembic upgrade head
python -m compileall -q src
test -s specs/event-driven-module-communication/execution/final-report.md
```

## Critérios de aceitação

- zero import/write cross-module
- metering/observability por Inbox
- Tool interna
- workers ativos
- zero FK cross-module
- relatório completo

## Rollback

- desativar consumers novos e reativar feature flag antiga durante janela controlada
- reconciliar por correlation/idempotency
