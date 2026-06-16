# Compatibility Map

Levantamento em: 2026-06-16

## Legacy → Target event mapping

### Agent (Tool domain)
| Legacy event | Target event | Direção |
|---|---|---|
| `tools.tool.created` | `agent.tool.created.v1` | agent lê ambos |
| `tools.tool.updated` | `agent.tool.updated.v1` | agent lê ambos |
| `tools.tool.status_changed` | `agent.tool.status_changed.v1` | agent lê ambos |
| `tools.secret.created` | `agent.secret.created.v1` | agent lê ambos |

### Eventos não versionados → versionados
| Evento atual (sem versão) | Target versionado | Produtor |
|---|---|---|
| `runtime.ask.completed` | `agent.execution.completed.v1` | agent |
| `tool_call` | `agent.execution.tool_completed.v1` | agent |
| `llm_call` | `agent.execution.llm_completed.v1` | agent |
| `info` | `agent.execution.started.v1` / `agent.execution.fallback_triggered.v1` | agent |

## Estratégia de compatibilidade

1. Agente publica eventos no formato target (`agent.execution.*.v1`)
2. Durante transição, agente também aceita eventos legacy via `TOOLS_LEGACY_EVENT_MAP`
3. Consumidores (metering, observability) subscribem apenas eventos target
4. Após cutover, legacy event map é removido
5. Handlers que apenas logam "Routing event" são substituídos por implementações reais

## Eventos sem consumidor

| Evento | Situação |
|---|---|
| `billing.*.v1` | Apenas self-subscription; sem consumidor externo |
| `core.*.v1` | Apenas self-subscription; sem consumidor externo |
| `identity.*.v1` | Apenas self-subscription; sem consumidor externo |
| `metering.*.v1` | Apenas self-subscription; sem consumidor externo |
| `observability.*.v1` | Apenas self-subscription; sem consumidor externo |

## Timeline de remoção

| Item | Spec de remoção |
|---|---|
| Legacy event map (tools.*) | 019 |
| Self-subscriptions billing/core/identity | 016 |
| Eventos não versionados em use cases | 008-010 |
