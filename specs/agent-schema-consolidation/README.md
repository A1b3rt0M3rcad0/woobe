# Consolidação de Schemas do Bounded Context Agent — ProjectRAI

## Objetivo

Migrar todas as tabelas de negócio atualmente distribuídas pelos schemas PostgreSQL `ai`, `knowledge` e `runtime` para o schema canônico `agent`, preservando dados, contratos e disponibilidade. Ao final, os três schemas legados deixam de existir.

## Branch

A implementação deve ocorrer exclusivamente em `development_agent-schema-consolidation`, criada a partir de `development`. O baseline observado para este plano foi `537e401356f956e928d1a7d025a3d9ccff2222aa`.

## Diagnóstico da branch development

A branch `development` já consolidou o código em `src/modules/agent`, mas a consolidação física não foi concluída:

- `ProviderCredentialModel`, `AgentModel`, prompts, contracts, configs, releases e tests continuam em `schema="ai"`;
- collections, documents, chunks e knowledge versions continuam em `schema="knowledge"`;
- sessions, messages e ask jobs continuam em `schema="runtime"`;
- o schema `agent` contém somente `agent_outbox_events` e `agent_inbox_events`;
- existem FKs entre as três áreas legadas e FKs cross-module para `core`, `identity`, `tools`, `metering` e `observability`;
- migrations 0001/0002 criam os schemas/tabelas legados, enquanto 0013/0014 apenas adicionam mensageria no schema agent.

## Estado final obrigatório

```text
agent.provider_credentials
agent.agents
agent.agent_prompts
agent.agent_contracts
agent.agent_model_configs
agent.agent_releases
agent.agent_release_tests
agent.document_collections
agent.agent_collections
agent.documents
agent.document_chunks
agent.knowledge_versions
agent.sessions
agent.messages
agent.ask_jobs
agent.agent_outbox_events
agent.agent_inbox_events
```

A lista deve ser ampliada se o inventário encontrar outras tabelas pertencentes ao bounded context.

## Política de Foreign Keys

- FK `agent.* -> agent.*`: permitida.
- FK `agent.* -> outro_schema.*`: proibida.
- FK `outro_schema.* -> agent.*`: proibida.
- UUID externo sem constraint, com índice local: permitido.

## Estratégia

O pacote usa expand-migrate-contract:

1. inventário e guards;
2. preflight;
3. move físico por `ALTER TABLE ... SET SCHEMA`;
4. views legadas temporárias quando necessárias;
5. atualização da metadata e código;
6. remoção de FKs cross-module;
7. consolidação de Inbox/Outbox;
8. cutover e observação;
9. drop sem `CASCADE` dos schemas antigos;
10. validação final.

## Regra de migrations históricas

O modo padrão é `append_only`. Migrations já aplicadas não são reescritas. Um banco vazio pode criar objetos legados transitoriamente durante `upgrade head`, mas o catálogo final deve conter somente `agent`. Rebaseline só é permitido com prova formal de que nenhum ambiente persistente depende dos revisions atuais.

## Quantidade de specs

18 specs numeradas (`000` a `017`), dentro do limite solicitado de 20.

## Execução

```bash
git checkout development_agent-schema-consolidation
test "$(git branch --show-current)" = "development_agent-schema-consolidation"
git merge-base --is-ancestor 537e401356f956e928d1a7d025a3d9ccff2222aa HEAD
```

Executar uma spec por vez, seguindo `MANIFEST.md` e registrando evidências em `execution/runtime.md`.
