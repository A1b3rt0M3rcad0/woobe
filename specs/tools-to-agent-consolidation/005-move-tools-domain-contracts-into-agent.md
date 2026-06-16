# 005 — Mover contratos de domínio de tools para agent

**Status:** pending  
**Tipo:** refactor  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Incorporar Tool, ToolSecret, enums, erros, eventos e interfaces de repository ao domínio de `agent`.

## Contexto observado

Tool possui `agent_id`; Secret é project-scoped e usado por ferramentas. Ambos viram capabilities internas de agent, sem imports reversos.

## Pré-condições

- spec 004 verde
- mapa aprovado

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
rg -n "from modules\.tools\.domain|import modules\.tools\.domain" src tests
sed -n "1,260p" src/modules/tools/domain/entities.py
sed -n "1,260p" src/modules/tools/domain/repositories.py
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- src/modules/agent/domain/**
- tests/unit/agent/**
- shims listados

## Alterações proibidas

- infra no domain
- agent importando modules.tools
- expor encrypted_value

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

1. Integrar Tool e ToolSecret no domínio agent.
2. Mover enums/erros/invariantes preservando valores.
3. Mover repositories interfaces.
4. Definir eventos `agent.tool.*.v1` e `agent.tool_secret.*.v1`.
5. Atualizar imports e shims temporários mínimos.

## Testes obrigatórios

- entidades/enums
- evento sem plaintext
- serialização compatível

## Validação

```bash
ruff check src/modules/agent/domain tests/unit/agent
pytest tests/unit/agent -q
pytest tests/architecture -q
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- domain agent não importa tools
- IDs/enums preservados
- eventos sem segredo

## Rollback

- restaurar imports legados antes do cutover

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
