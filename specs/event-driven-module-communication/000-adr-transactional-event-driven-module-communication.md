# 000 — ADR — comunicação cross-module por eventos transacionais

**Status:** accepted
**Tipo:** architecture
**Branch de execução:** `development_event-driven-module-communication`
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Formalizar a fronteira entre chamada interna e integração entre bounded contexts, tornando Outbox/Inbox o único mecanismo para efeitos cross-module.

## Situação observada

Na baseline atual, Tool já reside em `modules.agent`; portanto Agent→Tool é chamada interna. Em contraste, o `agent` ainda grava em `metering` e `observability` por adapters que importam entidades e repositories desses módulos e reutilizam a transação do agent.

## Pré-condições

- checkout limpo da branch dedicada
- baseline SHA validada
- nenhuma alteração produtiva anterior

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
rg -n "import_module\(\"modules\.|from modules\.(metering|observability|billing|core|identity)" src/modules
rg -n "MeteringUsageRecorder|ObservabilityTraceRecorder|AgentToolExecutor" src tests
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- esta spec
- execution/runtime.md
- execution/inventory/decision-log.md

## Alterações proibidas

- alterar código produtivo
- separar Tool novamente
- introduzir request/reply via broker para Tool interna

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

1. Registrar a decisão accepted.
2. Classificar Agent→Tool como síncrono interno.
3. Classificar Agent→Metering e Agent→Observability como integrações assíncronas obrigatórias.
4. Proibir imports/repositories/UoWs de outro módulo para alterar estado.
5. Definir consistência eventual para projeções e métricas.

## Testes obrigatórios

- checagem documental sem contradições
- manifesto depende do ADR

## Validação

```bash
python - <<'PY2'
from pathlib import Path
p=Path('specs/event-driven-module-communication/000-adr-transactional-event-driven-module-communication.md')
t=p.read_text().lower()
for x in ['outbox','inbox','bounded context','cross-module','tool']:
    assert x in t
print('ok')
PY2
```

## Critérios de aceitação

- regra interna versus cross-module inequívoca
- Agent→Tool não usa broker
- efeitos externos do agent usam Outbox

## Rollback

- antes da implementação, reverter somente o ADR
- depois, seguir rollback das specs técnicas
