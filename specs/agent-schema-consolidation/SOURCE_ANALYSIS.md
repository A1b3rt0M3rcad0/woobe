# Source Analysis — development

## Referência

- Repositório: `A1b3rt0M3rcad0/ProjectRAI`
- Baseline: `development`
- SHA observado: `537e401356f956e928d1a7d025a3d9ccff2222aa`
- Branch-alvo proposta: `development_agent-schema-consolidation`

## Evidências principais

1. `src/modules/agent/infra/database/models.py` mantém tabelas agent/AI em `schema="ai"`, incluindo `agents`, credentials, prompts, contracts, configs e releases.
2. O mesmo arquivo mantém collections/documents/chunks/knowledge_versions em `schema="knowledge"`.
3. Sessions/messages/ask_jobs seguem em `schema="runtime"`.
4. O schema `agent` aparece apenas nas tabelas `agent_outbox_events` e `agent_inbox_events`.
5. `migrations/versions/0001_create_schemas.py` cria `ai`, `knowledge` e `runtime` e não inclui `agent` na lista inicial.
6. `migrations/versions/0002_create_all_tables.py` cria as tabelas de negócio nos schemas legados e estabelece FKs entre eles.
7. `migrations/versions/0013_create_agent_outbox_events.py` cria o schema agent e sua Outbox, confirmando que o schema novo já existe, mas ainda não é owner das entidades.
8. `migrations/env.py` já importa apenas `modules.agent` para esse bounded context; portanto a divergência principal agora é física/metadata, não de bootstrap modular.

## Riscos técnicos

- locks de `ALTER TABLE SET SCHEMA`;
- colisões de índices/constraints no schema destino;
- FKs externas preservadas por OID após o move, contrariando a arquitetura;
- seis tabelas Inbox/Outbox legadas com nomes colidentes;
- eventos pending/retryable não podem ser descartados;
- pgvector, índices vetoriais, views, grants, triggers ou RLS não inventariados;
- código/raw SQL ainda qualificado com schema antigo;
- fresh install e upgrade incremental produzirem catálogos diferentes.

## Decisão

A correção deve ser feita por migrations append-only, com move físico e compatibilidade temporária, nunca por drop/create cego ou cópia sem validação.
