# Decision Log

## 000 — ADR — incorporar tools ao bounded context agent

**Status:** accepted
**Date:** 2026-06-16
**Spec:** 000

### Decision

Formalizar que ferramentas executadas por agentes e seus segredos de integração passam a pertencer ao bounded context `agent`, eliminando o módulo independente `tools` no estado final.

### Key points

- `agent` é definido como proprietário de Tool, ToolSecret, execução, políticas de risco e associação agente-ferramenta.
- `tools` deixa de existir como módulo e schema no estado final.
- HTTP e eventos são preservados durante transição.
- Segredos são tratados como capability interna restrita.

### Alternatives considered

- Manter `tools` como módulo separado com comunicação via eventos: rejeitado porque `Tool` possui `agent_id`, a execução participa do runtime dos agentes e a separação cria fronteira artificial.

### Consequences

- Todo o código de tools será movido para `src/modules/agent` sob `agent.tools` e `agent.tool_secrets`.
- O schema `tools` será eliminado; tabelas migradas para schema `agent`.
- Rotas atuais devem permanecer compatíveis durante cutover.
- Inbox/Outbox legadas de `tools` não podem ser descartadas com eventos pendentes.
- Nenhuma FK cross-module será criada.
- Segredos nunca aparecerão em logs, eventos, respostas HTTP, fixtures, snapshots ou mensagens de erro.
