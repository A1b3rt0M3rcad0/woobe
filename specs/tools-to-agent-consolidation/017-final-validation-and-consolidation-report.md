# 017 — Validação final e relatório de consolidação

**Status:** pending  
**Tipo:** validation  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Provar término sem dependências, schemas, FKs ou runtime paralelos e produzir relatório auditável.

## Contexto observado

Conclusão exige evidência de código, banco, API, mensageria, segurança e testes.

## Pré-condições

- spec 016 concluída

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
git status --short
rg -n "modules\.tools|schema.?=.tools.|ForeignKey\(.+tools|tools\.(tools|secrets|outbox_events|inbox_events)" src tests migrations scripts || true
find src/modules/agent -type f | sort
alembic current
alembic heads
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- execution/final-report.md
- execution/runtime.md
- docs arquitetura

## Alterações proibidas

- alterar função para passar
- ocultar falha
- concluir pendência

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

1. Executar suite completa.
2. Queries ownership/FKs/views/tabelas/schemas.
3. Comparar OpenAPI.
4. Validar eventos/workers/retry/idempotência.
5. Validar Tool/ToolSecret no AgentUnitOfWork.
6. Listar riscos/débitos.
7. Relatório com SHA/migrations/comandos.

## Testes obrigatórios

- full suite
- DB architecture
- OpenAPI
- security
- messaging concurrency

## Validação

```bash
ruff check src tests
pytest -q
alembic upgrade head
python -m compileall -q src
test ! -d src/modules/tools
test -s specs/tools-to-agent-consolidation/execution/final-report.md
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- 18 specs comprovadas
- zero módulo/schema tools
- zero FK cross-module
- API/eventos compatíveis
- relatório completo

## Rollback

- reabrir spec responsável; não concluir suite

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
