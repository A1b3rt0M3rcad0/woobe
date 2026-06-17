# Event Catalog Current

Levantamento em: 2026-06-16

## Eventos produzidos pelo módulo agent

### Domain events (agent/domain/events.py)
| Event Type | Versão |
|---|---|
| agent.execution.requested | v1 |
| agent.execution.completed | v1 |
| agent.execution.failed | v1 |
| agent.tool.created | v1 |
| agent.tool.updated | v1 |
| agent.tool.status_changed | v1 |
| agent.secret.created | v1 |
| agent.knowledge.document_indexed | v1 |
| agent.execution.fallback_triggered | v1 |

### Use case events (agent/application/use_cases/)
| Event Type | Origem |
|---|---|
| provider_credential.created | ai_use_cases |
| provider_credential.updated | ai_use_cases |
| agent.created | ai_use_cases |
| agent.updated | ai_use_cases |
| knowledge.collection.created | knowledge_use_cases |
| knowledge.document.uploaded | knowledge_use_cases |
| runtime.session.created | runtime_use_cases |
| runtime.ask.completed | runtime_use_cases, ask_use_case, ask_agent_stream_service |
| info | ask_use_case, ask_agent_stream_service, observability_trace_recorder |
| tool_call | ask_use_case, ask_agent_stream_service |
| llm_call | ask_use_case, ask_agent_stream_service |

### Adaptador metering_usage_recorder
| Event Type | Origem |
|---|---|
| metering_enums.UsageEventType.llm_request | agent/infra/adapters/metering_usage_recorder |

### Adaptador observability_trace_recorder
| Event Type | Origem |
|---|---|
| obs_enums.TraceEventType.info | agent/infra/adapters/observability_trace_recorder |
| tool_call | observability_trace_recorder |
| info | observability_trace_recorder |

## Eventos consumidos (Inbox handlers)

| Módulo | Handler registration |
|---|---|
| agent | inbox_handlers.py — implementação real |
| billing | **No handler registered** |
| core | **No handler registered** |
| identity | **No handler registered** |
| metering | **No handler registered** |
| observability | **No handler registered** |

## Routing keys / queues

Encontrado em `agent/infra/messaging/consumers.py`:
- Parâmetros: `queue_name`, `routing_keys` configuráveis

## Observações

- Eventos versionados (.v1) presentes apenas nos domain events do agent
- Eventos em use cases e adapters não seguem o formato `<producer>.<capability>.<fact>.vN`
- Nenhum consumidor real registrado fora do agent (todos handlers em outros módulos são no-op)
