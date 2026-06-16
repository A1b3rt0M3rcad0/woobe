# 004 — Adicionar guards e testes de caracterização antes da migração

**Status:** pending  
**Tipo:** testing  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Congelar comportamento, HTTP, eventos, segurança e fronteiras antes das mudanças.

## Contexto observado

A migração altera namespace Python, UoW, schema, mensageria e execução externa; sem caracterização, regressões ficam ocultas.

## Pré-condições

- spec 003 concluída

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
find tests -type f | sort
rg -n "tools|Tool|Secret|/tools|tools\." tests
pytest --collect-only -q
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- tests/architecture/**
- tests/contract/**
- tests/integration/tools/**
- tests/unit/tools/**

## Alterações proibidas

- alterar comportamento produtivo
- afrouxar asserts

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

1. Capturar OpenAPI e rotas.
2. Caracterizar eventos/payloads.
3. Cobrir lifecycle Tool/Secret.
4. Cobrir HTTP, timeout e erro.
5. Impedir plaintext em respostas/logs/eventos.
6. Criar allowlist temporária de imports.
7. Criar guard de FK/schema.

## Testes obrigatórios

- API/eventos caracterizados
- segredos protegidos
- allowlist explícita

## Validação

```bash
pytest tests/architecture -q
pytest tests/contract -q
pytest tests/unit/tools -q
pytest tests/integration/tools -q
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- baseline verde ou falhas documentadas
- regressões detectáveis

## Rollback

- remover testes adicionados; sem mudança produtiva

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
