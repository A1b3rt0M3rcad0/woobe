# ProjectRAI — Tools to Agent Consolidation

Pacote com **18 specs** para incorporar `tools` ao bounded context `agent`.

## Branch

`development_tools-to-agent-consolidation`, criada a partir de `development` no SHA `209cf8147f87a2e9949fec33a34429ab70f166b5`.

```bash
git switch development
git pull --ff-only
test "$(git rev-parse HEAD)" = "209cf8147f87a2e9949fec33a34429ab70f166b5" || echo "Revalidar baseline"
git switch -c development_tools-to-agent-consolidation
```

A branch não existia no remoto no momento da geração.

## Estado final

- código de ferramentas dentro de `modules.agent`;
- `agent.tools` e `agent.tool_secrets`;
- AgentUnitOfWork e Inbox/Outbox agent;
- rotas atuais preservadas durante cutover;
- nenhum `src/modules/tools`;
- nenhum schema `tools`;
- nenhuma FK cross-module.

Não copiar o módulo inteiro para um subdiretório mantendo UoW/Outbox paralelos.
