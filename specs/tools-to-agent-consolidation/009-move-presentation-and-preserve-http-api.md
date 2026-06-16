# 009 — Mover controllers, composers, schemas e rotas preservando API

**Status:** pending  
**Tipo:** refactor  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Transferir presentation de tools para agent sem alterar URLs/contratos no cutover.

## Contexto observado

As rotas atuais expõem gestão, teste, execução, associação por agente e segredos. Refactor estrutural não deve redesenhar API silenciosamente.

## Pré-condições

- spec 008 concluída
- OpenAPI baseline disponível

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
sed -n "1,220p" src/modules/tools/presentation/routes.py
find src/modules/tools/presentation -type f | sort
rg -n "include_router|tools_router" src/main.py src
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- src/modules/agent/presentation/**
- src/modules/agent/application/composers/**
- tests/contract/**

## Alterações proibidas

- renomear endpoints
- alterar status/envelopes
- expor segredo

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

1. Mover controllers/schemas.
2. Mover composers para AgentUnitOfWork/ports.
3. Integrar router em modules.agent mantendo paths efetivos.
4. Atualizar bootstrap.
5. Manter aliases/deprecation explícitos se necessário.
6. Comparar OpenAPI.

## Testes obrigatórios

- todas as rotas
- OpenAPI diff
- sem encrypted_value
- auth/escopo

## Validação

```bash
pytest tests/contract -q
pytest tests/integration/agent -q
python -m compileall -q src
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- paths/métodos/payloads compatíveis
- bootstrap sem presentation tools após cutover
- sem vazamento

## Rollback

- reativar router antigo antes da remoção

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
