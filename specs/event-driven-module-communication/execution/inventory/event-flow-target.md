# Event Flow Target

Levantamento em: 2026-06-16

## Fluxo alvo cross-module

```
state + Outbox (agent) → dispatcher → RabbitMQ → consumer (metering/observability) 
→ Inbox persist → ACK → processor → use case consumidor → state + Inbox processed
```

## Produtor: agent

### Eventos de execução (lifecycle)
| Evento | Versão | Consumidor alvo | Handler alvo | Efeito |
|---|---|---|---|---|
| `agent.execution.requested` | v1 | metering | metering: handle_execution_requested | Registrar solicitação de execução |
| `agent.execution.started` | v1 | metering, observability | metering: handle_execution_started; observability: handle_trace_started | Iniciar trace/medição |
| `agent.execution.llm_completed` | v1 | metering, observability | metering: handle_llm_request; observability: handle_llm_call | Registrar uso de LLM e trace |
| `agent.execution.tool_completed` | v1 | metering, observability | metering: handle_tool_execution; observability: handle_tool_call | Registrar tool execution e trace |
| `agent.execution.fallback_triggered` | v1 | metering, observability | metering: handle_fallback; observability: handle_trace_fallback | Registrar fallback |
| `agent.execution.completed` | v1 | metering, observability | metering: handle_execution_completed; observability: handle_trace_completed | Finalizar medição/trace |
| `agent.execution.failed` | v1 | metering, observability | metering: handle_execution_failed; observability: handle_trace_failed | Finalizar com falha |

### Eventos de domínio internos (Tool)
| Evento | Versão | Consumidor | Justificativa |
|---|---|---|---|
| `agent.tool.created` | v1 | agent (self) | Self-subscription justificada: Tool lifecycle interno do agent |
| `agent.tool.updated` | v1 | agent (self) | Self-subscription justificada |
| `agent.tool.status_changed` | v1 | agent (self) | Self-subscription justificada |
| `agent.secret.created` | v1 | agent (self) | Self-subscription justificada |

### Eventos de domínio internos (Knowledge)
| Evento | Versão | Consumidor |
|---|---|---|
| `agent.knowledge.document_indexed` | v1 | agent (self) |

### Legacy events (compatibilidade)
| Legacy | Target | Consumidor |
|---|---|---|
| `tools.tool.created` | `agent.tool.created.v1` | agent (self) |
| `tools.tool.updated` | `agent.tool.updated.v1` | agent (self) |
| `tools.tool.status_changed` | `agent.tool.status_changed.v1` | agent (self) |
| `tools.secret.created` | `agent.secret.created.v1` | agent (self) |

## Consumidores sem caso de uso real (remover ou justificar)

| Módulo | Self-binding | Eventos listados | Ação |
|---|---|---|---|
| billing | `billing.#` | `billing.*` events | Remover consumer ou justificar com caso de uso real |
| core | `core.#` | `core.*` events | Remover consumer ou justificar com caso de uso real |
| identity | `identity.#` | `identity.*` events | Remover consumer ou justificar com caso de uso real |

## Regras

- Agent não consome eventos próprios de Tool via broker — apenas por self-subscription justificada
- Metering e observability NÃO se inscrevem nos próprios eventos — apenas nos eventos do agent
- Todo evento cross-module segue o formato `<producer>.<capability>.<fact>.vN`
- Payloads mínimos com apenas informações necessárias ao consumidor
