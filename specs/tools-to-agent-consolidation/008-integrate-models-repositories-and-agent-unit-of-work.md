# 008 — Integrar models, mappers, repositories e AgentUnitOfWork

**Status:** pending  
**Tipo:** refactor  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Mover persistência Tool/ToolSecret para agent e eliminar ToolsUnitOfWork.

## Contexto observado

ToolsUnitOfWork e models no schema tools criam transação e Outbox separadas para capacidade do agent.

## Pré-condições

- specs 005-007 concluídas

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
sed -n "1,260p" src/modules/tools/infra/database/models.py
sed -n "1,260p" src/modules/tools/infra/database/unit_of_work.py
find src/modules/tools/infra/database -type f -maxdepth 2 -print
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- src/modules/agent/infra/database/**
- src/modules/agent/application/composers/**
- tests/integration/agent/**

## Alterações proibidas

- AgentToolsUnitOfWork
- models duplicados
- FK para core/identity
- Outbox separada

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

1. Adicionar ToolModel/ToolSecretModel ao metadata agent.
2. Usar agent.tools e agent.tool_secrets.
3. Mover mappers/repositories.
4. Adicionar tools/tool_secrets ao AgentUnitOfWork.
5. Usar Outbox canônica.
6. Atualizar composers.
7. Adicionar índices locais.

## Testes obrigatórios

- repository integration
- commit/rollback
- outbox atomicity
- metadata uniqueness

## Validação

```bash
ruff check src/modules/agent/infra/database tests
pytest tests/integration/agent -q
pytest tests/architecture -q
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- um UoW
- models agent.*
- sem FK cross-module
- rollback atômico

## Rollback

- manter repositories antigos atrás de shim; sem dual-write implícito

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
