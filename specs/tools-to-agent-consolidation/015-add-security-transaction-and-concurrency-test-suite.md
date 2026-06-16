# 015 — Adicionar suíte completa de segurança, transação e concorrência

**Status:** pending  
**Tipo:** testing  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Fechar cobertura antes da remoção legada.

## Contexto observado

Execução HTTP e segredos elevam impacto de bugs; CRUD não basta.

## Pré-condições

- spec 014 concluída

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
pytest --collect-only -q
rg -n "tool|secret|ssrf|timeout|idempot|concurr|rollback" tests
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- tests/unit/agent/**
- tests/integration/agent/**
- tests/contract/**
- tests/e2e/**
- tests/architecture/**
- tests/migrations/**

## Alterações proibidas

- desabilitar flakey sem causa
- segredo real
- network pública

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

1. Cobrir todos use cases.
2. Tool+Outbox transaction.
3. Inbox/Outbox concurrency.
4. HTTP fake local.
5. timeout/retry/redaction.
6. secret por project/name.
7. isolamento/autorização.
8. migrations fresh/upgrade.
9. ausência imports/schema/FKs.

## Testes obrigatórios

- unit
- integration
- contract
- e2e
- architecture
- migration
- security

## Validação

```bash
ruff check src tests
pytest tests/unit/agent -q
pytest tests/integration/agent -q
pytest tests/contract -q
pytest tests/architecture -q
pytest tests/migrations -q
pytest tests/e2e -q
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- todos grupos verdes
- sem network pública
- segredo fake não aparece

## Rollback

- falhas bloqueiam destrutivas

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
