# Subscription Matrix

Levantamento em: 2026-06-16

## Estado atual (self-subscriptions)

| Módulo | Routing keys | Exchange | Queue | Tipo |
|---|---|---|---|---|
| agent | `["agent.#"]` | — | configurável | self-subscription |
| billing | `["billing.#"]` | — | configurável | self-subscription (sem caso de uso real) |
| core | `["core.#"]` | — | configurável | self-subscription (sem caso de uso real) |
| identity | `["identity.#"]` | — | configurável | self-subscription (sem caso de uso real) |
| metering | — | — | — | registry vazio (pass) |
| observability | — | — | — | registry vazio (pass) |

## Estado alvo

### Agent subscriptions
| Routing key | Justificativa |
|---|---|
| `agent.tool.created.v1` | Self-subscription: Tool lifecycle interno |
| `agent.tool.updated.v1` | Self-subscription |
| `agent.tool.status_changed.v1` | Self-subscription |
| `agent.secret.created.v1` | Self-subscription |
| `tools.tool.created` | Legacy compatibility |
| `tools.tool.updated` | Legacy compatibility |
| `tools.tool.status_changed` | Legacy compatibility |
| `tools.secret.created` | Legacy compatibility |

### Metering subscriptions
| Routing key | Evento do producer | Handler |
|---|---|---|
| `agent.execution.requested.v1` | agent | handle_execution_requested |
| `agent.execution.started.v1` | agent | handle_execution_started |
| `agent.execution.llm_completed.v1` | agent | handle_llm_request |
| `agent.execution.tool_completed.v1` | agent | handle_tool_execution |
| `agent.execution.fallback_triggered.v1` | agent | handle_fallback |
| `agent.execution.completed.v1` | agent | handle_execution_completed |
| `agent.execution.failed.v1` | agent | handle_execution_failed |

### Observability subscriptions
| Routing key | Evento do producer | Handler |
|---|---|---|
| `agent.execution.started.v1` | agent | handle_trace_started |
| `agent.execution.llm_completed.v1` | agent | handle_llm_call |
| `agent.execution.tool_completed.v1` | agent | handle_tool_call |
| `agent.execution.fallback_triggered.v1` | agent | handle_trace_fallback |
| `agent.execution.completed.v1` | agent | handle_trace_completed |
| `agent.execution.failed.v1` | agent | handle_trace_failed |

### Identity/Core/Billing
| Módulo | Ação |
|---|---|
| billing | Remover self-subscription OU implementar consumo real de eventos do agent |
| core | Remover self-subscription OU implementar consumo real de eventos do agent |
| identity | Remover self-subscription OU implementar consumo real de eventos do agent |

## Regras de bindings

- Queue bindings representam eventos externos REALMENTE consumidos
- Self-subscription permitida apenas para tool events (agent)
- Nenhum módulo deve se inscrever no próprio prefixo sem justificativa explícita
