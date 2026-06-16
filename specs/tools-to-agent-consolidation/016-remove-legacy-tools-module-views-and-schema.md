# 016 — Remover módulo, shims, views e schema tools

**Status:** pending  
**Tipo:** cleanup  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Executar contract e eliminar artefatos legados após cutover.

## Contexto observado

Compatibilidade não é estado final: módulo, views e schema devem desaparecer.

## Pré-condições

- spec 015 verde
- go/no-go aprovado
- zero pendentes
- backup verificado

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
test -d src/modules/tools && find src/modules/tools -type f | sort || true
rg -n "modules\.tools|schema.?=.tools.|tools\." src tests migrations scripts
psql "$PROJECTRAI_DATABASE_URL" -c "SELECT nspname FROM pg_namespace WHERE nspname='tools';" || true
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- remoção src/modules/tools
- migration contract nova
- remoção shims/allowlists
- tests

## Alterações proibidas

- DROP SCHEMA CASCADE
- schema com dependências
- apagar backup cedo

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

1. Remover imports/shims.
2. Remover diretório tools.
3. Remover compat views sem dependências.
4. DROP SCHEMA tools sem CASCADE.
5. Atualizar fresh-install expectations.
6. Guard de ausência total.

## Testes obrigatórios

- absence architecture
- DB dependencies
- fresh install
- upgrade previous
- API regression

## Validação

```bash
ruff check src tests
pytest -q
alembic upgrade head
python -m compileall -q src
test ! -d src/modules/tools
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- módulo ausente
- schema ausente
- rotas via agent
- sem referência fora histórico autorizado

## Rollback

- rollback recria schema/views e restaura módulo; reconciliar dados novos

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
