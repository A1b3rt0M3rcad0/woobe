# 002 — Definir arquitetura-alvo e mapa current-to-target

**Status:** pending  
**Tipo:** architecture  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Definir onde cada responsabilidade de `tools` ficará dentro de `modules.agent`, evitando um submódulo legado disfarçado.

## Contexto observado

Copiar `src/modules/tools` para `src/modules/agent/tools` manteria duplicação de UoW, Outbox e composição. A arquitetura-alvo deve integrar contratos ao domínio/aplicação de agent e usar capability packages apenas para organização interna.

## Pré-condições

- spec 001 concluída

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
find src/modules/agent -maxdepth 5 -type f | sort
rg -n "class AgentUnitOfWork|ToolExecution|ToolCall|tool_calls" src/modules/agent tests
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- execution/inventory/current-to-target.md
- execution/inventory/target-tree.md
- execution/inventory/public-api-contract.md

## Alterações proibidas

- skeleton vazio
- segundo UoW/Outbox
- novo bounded context

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

1. Mapear Tool e ToolSecret para domain agent.
2. Mapear DTOs/use cases para application agent.
3. Mapear HTTP/secret resolution para ports/adapters.
4. Mapear persistence para infra/database.
5. Mapear presentation e workers.
6. Definir `agent.tools` e `agent.tool_secrets`.
7. Definir shims temporários e prazo.

## Testes obrigatórios

- cada item do inventário possui destino
- target sem UoW/Outbox paralelos

## Validação

```bash
python - <<'PY'
from pathlib import Path
p=Path("specs/tools-to-agent-consolidation/execution/inventory/current-to-target.md")
assert p.exists() and p.stat().st_size>0
t=p.read_text(); assert "ToolsUnitOfWork" in t and "agent.tool_secrets" in t
print("ok")
PY
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- destino explícito para todos os itens
- sem AgentToolsUnitOfWork
- tabelas finais definidas

## Rollback

- reverter documentos antes da implementação

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
