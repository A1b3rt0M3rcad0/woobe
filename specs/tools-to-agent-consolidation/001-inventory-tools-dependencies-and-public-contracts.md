# 001 — Inventariar tools, dependências e contratos públicos

**Status:** pending  
**Tipo:** discovery  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Criar inventário verificável de arquivos, imports, rotas, eventos, workers, tabelas, constraints, consumidores e integrações de `tools`.

## Contexto observado

O módulo contém domínio, DTOs, casos de uso, composers, controllers, repositories, UoW e persistência próprios; publica eventos `tools.*`, expõe API e armazena segredos criptografados.

## Pré-condições

- spec 000 concluída

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
find src/modules/tools -type f | sort
rg -n "modules\.tools" src tests migrations frontend
rg -n "tools\.(tool|secret)|routing_key|event_type" src tests
rg -n "ToolRepository|SecretRepository|ToolsUnitOfWork|ToolModel|SecretModel" src tests
rg -n "/tools|/agents/\{agent_id\}/tools|/secrets" src tests frontend
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- execution/inventory/tools-files.md
- execution/inventory/tools-imports.md
- execution/inventory/tools-api.md
- execution/inventory/tools-events.md
- execution/inventory/tools-database.md

## Alterações proibidas

- alterar código produtivo
- renomear arquivos
- alterar migrations

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

1. Listar e classificar arquivos por camada.
2. Mapear imports de entrada e saída.
3. Registrar rotas, métodos, parâmetros, status e schemas.
4. Catalogar eventos, payloads e routing keys.
5. Catalogar tabelas, colunas, índices, unique constraints, FKs e volumes.
6. Mapear frontend, testes, seeds, jobs e scripts.
7. Classificar cada item como move, merge, rewrite, shim ou delete.

## Testes obrigatórios

- inventário com caminhos e contagens
- nenhuma referência sem classificação

## Validação

```bash
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-files.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-imports.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-api.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-events.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-database.md
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- 100% dos arquivos classificados
- rotas/eventos registrados
- consumidores identificados
- riscos de segredo registrados

## Rollback

- nenhum rollback; somente inventário

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
