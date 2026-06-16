# 014 — Executar cutover com shims temporários e observabilidade

**Status:** pending  
**Tipo:** cutover  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Trocar reads/writes/runtime para agent e remover dualidade operacional após janela observada.

## Contexto observado

Não manter dual-write indefinido. Cutover deve provar que HTTP, execução e eventos usam agent como fonte única.

## Pré-condições

- spec 013 verde
- migrations testadas
- rollback drill

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
rg -n "modules\.tools|tools\." src tests | sort
git status --short
alembic current
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- feature flags existentes
- telemetria
- shims temporários
- execution/cutover-report.md

## Alterações proibidas

- dual-write não idempotente
- silenciar falhas
- remover rollback cedo

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

1. Ativar composers/router agent.
2. Ativar repositories/executor agent.
3. Ativar Outbox/Inbox/registry agent.
4. Medir erros, latência, timeout, retry, eventos.
5. Comparar counts.
6. Desativar paths legados.
7. Autorizar contract após go/no-go.

## Testes obrigatórios

- smoke E2E
- CRUD+execute+secret
- event delivery
- rollback drill

## Validação

```bash
pytest tests/contract -q
pytest tests/integration/agent -q
pytest tests/e2e -q
test -s specs/tools-to-agent-consolidation/execution/cutover-report.md
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- agent fonte única
- SLO sem regressão inexplicada
- rollback testado
- go/no-go aprovado

## Rollback

- reverter flags/router/registry e views

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
