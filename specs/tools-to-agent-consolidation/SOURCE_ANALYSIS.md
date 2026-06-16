# SOURCE ANALYSIS — development

- Repository: `A1b3rt0M3rcad0/ProjectRAI`
- Branch: `development`
- HEAD observado: `209cf8147f87a2e9949fec33a34429ab70f166b5`
- Branch proposta: `development_tools-to-agent-consolidation`

## Evidência

- Tool possui `project_id` e `agent_id`, configuração, schemas, risco, timeout e status.
- Secret é project-scoped e armazena valor criptografado.
- O módulo possui CRUD, list, test e execute, publica `tools.tool.*` e `tools.secret.*`.
- Há API pública para tools, execução, teste, associação por agente e secrets.
- Persistência atual: `tools.tools`, `tools.secrets`, `tools.outbox_events`, `tools.inbox_events`.
- ToolsUnitOfWork cria fronteira transacional separada.
- O executor HTTP está no use case.
- A resolução de segredo atual é inconsistente: helper síncrono chama repository assíncrono sem project_id/name.

## Conclusão

A capacidade deve ser incorporada ao agent, mas não aninhada como arquitetura paralela. O target usa ports/adapters, AgentUnitOfWork, schema agent e mensageria canônica. Confiança alta para ownership e target; confiança média para consumidores externos de eventos, que devem ser inventariados antes de renomear routing keys.
