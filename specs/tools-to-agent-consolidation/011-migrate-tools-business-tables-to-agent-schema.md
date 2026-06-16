# 011 — Migrar tabelas tools e secrets para schema agent

**Status:** pending  
**Tipo:** database-migration  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Mover `tools.tools` e `tools.secrets` para `agent.tools` e `agent.tool_secrets`, preservando IDs, dados, constraints e índices.

## Contexto observado

Agent já é schema do bounded context. As tabelas business de tools ainda permanecem separadas.

## Pré-condições

- spec 008 concluída
- preflight aprovado
- head Alembic confirmado

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
alembic current
alembic heads
rg -n "schema=\"tools\"|tools\.tools|tools\.secrets" migrations src tests
psql "$PROJECTRAI_DATABASE_URL" -c "SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema IN ('tools','agent') ORDER BY 1,2;" || true
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- migration append-only nova
- scripts preflight/verification
- tests/migrations/**

## Alterações proibidas

- editar 0001/0002
- DROP CASCADE
- alterar UUIDs
- mover inbox/outbox junto

## Regras invariantes

- O estado final possui apenas `src/modules/agent` como proprietário das capacidades de ferramentas usadas por agentes.
- Não manter `tools` como bounded context independente no estado final.
- Não criar chamadas síncronas entre módulos para alteração de estado.
- Não criar Unit of Work que atravesse módulos distintos.
- Não criar Foreign Key física entre tabelas de módulos diferentes.
- Referências a `project_id`, `organization_id`, `user_id` ou IDs externos permanecem UUIDs opacos e indexados, sem FK cross-module.
- FKs internas dentro de `agent.*` são permitidas.
- Escritas de domínio e Outbox devem ocorrer na mesma transação do `AgentUnitOfWork`.
- Inbox/Outbox legadas de `tools` não podem ser descartadas com eventos pendentes.
- Rotas HTTP atuais devem permanecer compatíveis durante o cutover.
- Segredos nunca podem aparecer em logs, eventos, respostas HTTP, fixtures, snapshots ou mensagens de erro.
- Não editar migrations históricas já aplicadas; usar migrations append-only após o head observado.
- Não usar `DROP SCHEMA ... CASCADE`.
- Não marcar a spec como concluída sem evidências de validação e atualização de `execution/runtime.md`.


## Plano de implementação

1. Criar migration após head.
2. Preflight colisões.
3. SET SCHEMA de tools.tools.
4. SET SCHEMA de tools.secrets e rename para tool_secrets.
5. Recriar/renomear constraints/índices.
6. Criar FK interna tools.agent_id->agents.id somente sem órfãos; project_id sem FK.
7. Views temporárias se protocolo exigir.
8. Validar counts/IDs/hashes/sequences.

## Testes obrigatórios

- upgrade current head
- fresh install
- downgrade
- orphan
- count/hash

## Validação

```bash
alembic upgrade head
pytest tests/migrations -q
alembic downgrade -1
alembic upgrade head
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- dados preservados
- tabelas físicas agent
- sem FK cross-module
- downgrade testado

## Rollback

- downgrade restaura schema/nome sem perda

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
