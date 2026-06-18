# 017 — Remover Foreign Keys cross-module

**Status:** pending  
**Tipo:** database-boundary  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Alinhar o banco ao ownership por módulo, preservando referências lógicas e índices.

## Situação observada

A baseline ainda declara FKs core→identity, billing→identity, metering→core e observability→core.

## Pré-condições

- spec 016 concluída
- inventário de FKs aprovado

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
rg -n "ForeignKey\(\"(identity|core|agent|metering|billing|observability)\." src/modules
psql "$PROJECTRAI_DATABASE_URL" -c "SELECT conname, conrelid::regclass, confrelid::regclass FROM pg_constraint WHERE contype='f' ORDER BY 2;" || true
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- src/modules/*/infra/database/models.py
- migrations/versions/new_*
- tests/architecture/**
- tests/migrations/**

## Alterações proibidas

- remover coluna lógica
- join cross-module substituto
- DROP CASCADE

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

1. Classificar FKs internas/cross-module.
2. Remover constraints cross-module em migration append-only.
3. Remover ForeignKey dos models e manter UUID/index.
4. Criar projeção local apenas quando necessária.
5. Gerar orphan reports.
6. Bloquear autogenerate de reintroduzir FKs.

## Testes obrigatórios

- metadata scan
- pg_constraint
- upgrade/downgrade
- index preservation
- projection replay

## Validação

```bash
alembic upgrade head
pytest tests/architecture tests/migrations -q
alembic downgrade -1
alembic upgrade head
```

## Critérios de aceitação

- zero FK cross-module
- IDs preservados
- índices presentes
- zero join síncrono novo

## Rollback

- downgrade restaura constraint somente sem órfãos
