# 000 — ADR — incorporar tools ao bounded context agent

**Status:** pending  
**Tipo:** architecture  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Formalizar que ferramentas executadas por agentes e seus segredos de integração passam a pertencer ao bounded context `agent`, eliminando o módulo independente `tools` no estado final.

## Contexto observado

Na baseline, `Tool` possui `agent_id`, há rota de listagem por agente, e a execução de ferramentas participa diretamente do runtime dos agentes. Ao mesmo tempo, o módulo mantém UoW, Outbox, Inbox, rotas e schema próprios. Essa separação cria uma fronteira artificial.

## Pré-condições

- checkout limpo da branch dedicada
- baseline SHA validada
- nenhuma mudança funcional antes da aprovação do ADR

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
find src/modules/tools -maxdepth 5 -type f | sort
rg -n "modules\.tools|schema.?=.tools.|ForeignKey\(.+tools|tools\." src migrations tests
rg -n "/tools|agents/.+tools" src tests frontend || true
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- esta spec
- execution/runtime.md
- execution/inventory/decision-log.md

## Alterações proibidas

- mover arquivos
- alterar modelos
- alterar migrations
- mudar rotas ou eventos

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

1. Registrar decisão, alternativas e consequências.
2. Definir `agent` como proprietário de Tool, ToolSecret, execução, políticas de risco e associação agente-ferramenta.
3. Determinar que `tools` deixa de existir como módulo e schema.
4. Preservar HTTP e eventos durante transição.
5. Tratar segredos como capability interna restrita.

## Testes obrigatórios

- teste documental de consistência
- manifesto referencia ADR

## Validação

```bash
python - <<'PY'
from pathlib import Path
p=Path("specs/tools-to-agent-consolidation/000-adr-incorporate-tools-into-agent.md")
assert p.exists()
assert "módulo independente `tools`" in p.read_text()
print("ok")
PY
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- ownership sem ambiguidade
- estado final sem módulo/schema tools
- segurança de segredos explícita

## Rollback

- reverter ADR antes de implementação
- depois, seguir rollback de código e banco

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
