# 006 — Mover DTOs e casos de uso para application de agent

**Status:** pending  
**Tipo:** refactor  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Migrar gestão de ferramentas/segredos para application agent usando contratos e ports adequados.

## Contexto observado

Os casos de uso atuais misturam orchestration com HTTP, criptografia e templates. Isso não deve ser copiado.

## Pré-condições

- spec 005 concluída

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
find src/modules/tools/application -type f | sort
rg -n "httpx|encrypt_secret|decrypt_secret|os\.getenv|modules\.tools" src/modules/tools/application
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- src/modules/agent/application/**
- tests/unit/agent/**

## Alterações proibidas

- HTTP/SQLAlchemy/env em application
- DTO duplicado indefinido

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

1. Mover DTOs CRUD/list/test/execute.
2. Mover casos de uso CRUD.
3. Extrair ToolExecutionPort, SecretCipherPort e ToolSecretResolverPort.
4. Transformar test/execute em orchestration.
5. Preservar HTTP outputs.
6. Escrever evento na Outbox agent na mesma transação.

## Testes obrigatórios

- fake repositories/ports
- not-found
- outbox transacional
- DTO compatibility

## Validação

```bash
ruff check src/modules/agent/application tests/unit/agent
pytest tests/unit/agent -q
pytest tests/architecture -q
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- application sem httpx/SQLAlchemy/modules.tools
- UoW/repositories agent-owned
- contratos preservados

## Rollback

- composers podem voltar a use cases legados durante expand

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
