# 013 — Atualizar imports, bootstrap, Alembic e dependency injection

**Status:** pending  
**Tipo:** integration  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Fazer aplicação operar por modules.agent/agent.* com shims somente temporários.

## Contexto observado

Imports de bootstrap, Alembic, tests, seeds e scripts podem manter tools vivo mesmo após mover tabelas.

## Pré-condições

- specs 009-012 concluídas

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
rg -n "modules\.tools|schema.?=.tools.|tools\.(tools|secrets|outbox_events|inbox_events)" src migrations tests scripts
sed -n "1,140p" migrations/env.py
sed -n "1,140p" src/main.py
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- src/**
- migrations/env.py
- tests/**
- scripts/**
- config necessária

## Alterações proibidas

- API não relacionada
- metadata duplicado
- import wildcard duplicado

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

1. Atualizar bootstrap/router.
2. Atualizar Alembic env.
3. Atualizar composers/factories/tests/seeds/scripts.
4. Atualizar discovery/entrypoints.
5. Reduzir allowlist a zero/shim explícito.
6. Guard contra modules.tools/schema tools.

## Testes obrigatórios

- startup smoke
- Alembic metadata
- architecture guard
- route registration

## Validação

```bash
python -m compileall -q src
pytest tests/architecture -q
pytest tests/contract -q
alembic heads
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- app sem import tools
- metadata final uma vez
- sem nova referência schema tools

## Rollback

- reativar imports enquanto módulo/views existirem

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
