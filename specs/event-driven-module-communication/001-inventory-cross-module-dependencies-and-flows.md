# 001 — Inventário de imports, writes, eventos, workers e FKs

**Status:** pending  
**Tipo:** discovery  
**Branch de execução:** `development_event-driven-module-communication`  
**Baseline obrigatória:** `development` em `cd8d5867967fea25ea170bd88ebc9a461ed16c09`

## Objetivo

Criar uma matriz completa de todas as dependências e fluxos entre módulos.

## Situação observada

Há imports dinâmicos explícitos no agent, registries vazios, consumers que apenas varrem tabelas, handlers no-op, self-bindings e FKs cross-schema.

## Pré-condições

- spec 000 concluída

## Discovery obrigatório

```bash
test "$(git branch --show-current)" = "development_event-driven-module-communication"
git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD
git status --short
rg -n "from modules\.[a-z_]+|import modules\.[a-z_]+|import_module\(\"modules\." src/modules
rg -n "ForeignKey\(\"(identity|core|agent|metering|billing|observability)\." src/modules migrations
rg -n "INBOX_ROUTING_KEYS|routing_keys|queue_name|event_type=" src/modules
rg -n "pass$|Routing event|No handler registered" src/modules/*/infra/{messaging,workers} || true
```

Persistir evidências em `specs/event-driven-module-communication/execution/inventory/`. Ausência de banco, broker ou ferramenta é bloqueio; não inferir sucesso.

## Alterações permitidas

- execution/inventory/cross-module-imports.md
- execution/inventory/cross-module-writes.md
- execution/inventory/foreign-keys.md
- execution/inventory/worker-topology.md
- execution/inventory/event-catalog-current.md

## Alterações proibidas

- corrigir ocorrências durante inventário
- omitir import dinâmico
- presumir consumidor externo

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

1. Mapear imports estáticos e dinâmicos.
2. Mapear writes cross-module e UoWs compartilhados.
3. Mapear FKs e SQL cross-schema.
4. Mapear produtores, routing keys, filas, bindings, consumers, Inbox, processors e handlers.
5. Classificar cada item por severidade e spec de correção.

## Testes obrigatórios

- inventário cobre todos os módulos
- cada violação tem destino

## Validação

```bash
for f in cross-module-imports cross-module-writes foreign-keys worker-topology event-catalog-current; do test -s specs/event-driven-module-communication/execution/inventory/$f.md; done
```

## Critérios de aceitação

- zero dependência sem classificação
- topologia real documentada
- handlers no-op identificados

## Rollback

- nenhum rollback; discovery apenas
