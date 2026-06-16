# 003 — Definir protocolo incremental, compatibilidade e rollback

**Status:** pending  
**Tipo:** migration-planning  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Estabelecer fases expand, migrate, cutover e contract para código, banco, API e eventos.

## Contexto observado

A development já recebeu consolidação de schemas para agent por migrations append-only e views temporárias. A migração de tools deve seguir disciplina semelhante sem perpetuar compatibilidade.

## Pré-condições

- specs 001 e 002 concluídas

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
alembic heads
alembic history --verbose | tail -n 80
rg -n "CREATE OR REPLACE VIEW|SET SCHEMA|DROP SCHEMA" migrations/versions
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- execution/inventory/migration-protocol.md
- execution/inventory/rollback-matrix.md
- execution/inventory/cutover-checklist.md

## Alterações proibidas

- executar DDL
- editar migration histórica
- remover compatibilidade

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

1. Definir expand, migrate, cutover e contract.
2. Definir gates de eventos pendentes, divergência e downgrade.
3. Definir rollback de código, banco e mensageria.
4. Definir prazo/owner de shims e views.

## Testes obrigatórios

- go/no-go para cada fase
- rollback sem CASCADE/perda

## Validação

```bash
test -s specs/tools-to-agent-consolidation/execution/inventory/migration-protocol.md
test -s specs/tools-to-agent-consolidation/execution/inventory/rollback-matrix.md
test -s specs/tools-to-agent-consolidation/execution/inventory/cutover-checklist.md
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- fases e gates definidos
- compatibilidade com prazo
- rollback preserva dados

## Rollback

- remover documentos se ADR cancelada

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
