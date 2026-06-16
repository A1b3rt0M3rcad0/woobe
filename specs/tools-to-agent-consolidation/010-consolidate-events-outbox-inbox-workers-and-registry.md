# 010 — Consolidar eventos, Outbox, Inbox, workers e registry

**Status:** pending  
**Tipo:** messaging  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Migrar mensageria tools para infraestrutura agent preservando consumidores.

## Contexto observado

O módulo publica `tools.tool.*`/`tools.secret.*` em Outbox própria. Não pode haver duas fontes nem descarte de pendentes.

## Pré-condições

- specs 006,008,009 concluídas
- catálogo preenchido

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
find src/modules/tools -path "*worker*" -o -path "*messaging*" -o -name entrypoint.py | sort
rg -n "tools\.tool|tools\.secret|Outbox|Inbox|routing_key" src/modules/tools src/modules/agent tests
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- src/modules/agent/infra/messaging/**
- src/modules/agent/infra/workers/**
- src/modules/agent/entrypoint.py
- tests/integration/agent/**

## Alterações proibidas

- Outbox tools nova
- descartar pendentes
- plaintext
- rename sem compat

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

1. Mapear eventos para agent versionados.
2. Definir compat/dual-publish lógico só com consumidores comprovados.
3. Mover handlers/workers para agent.
4. Usar inbox/outbox agent.
5. Preservar idempotency.
6. Compat de routing com prazo.
7. Remover entrypoint tools após registry agent.

## Testes obrigatórios

- publisher
- inbox idempotency
- retry/DLQ
- routing compatibility
- redaction

## Validação

```bash
pytest tests/integration/agent -q
pytest tests/architecture -q
ruff check src/modules/agent/infra/messaging src/modules/agent/infra/workers
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- workers no agent
- pendentes transformáveis
- consumidores preservados

## Rollback

- voltar registry ao entrypoint tools enquanto compat existe

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
