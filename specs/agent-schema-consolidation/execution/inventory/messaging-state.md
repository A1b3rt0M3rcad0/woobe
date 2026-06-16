# Estado de Inbox/Outbox legadas

*Populado na spec 001 via análise estática. Estado real do banco pendente.*

## Tabelas de mensageria

### Schema `ai` (legado)
| Tabela | Modelo | Eventos esperados |
|---|---|---|
| `ai.outbox_events` | `AiOutboxEventModel` | Eventos de agente (pré-consolidação) |
| `ai.inbox_events` | `AiInboxEventModel` | Eventos recebidos |

### Schema `knowledge` (legado)
| Tabela | Modelo | Eventos esperados |
|---|---|---|
| `knowledge.outbox_events` | `KnowledgeOutboxEventModel` | Eventos de conhecimento |
| `knowledge.inbox_events` | `KnowledgeInboxEventModel` | Eventos recebidos |

### Schema `runtime` (legado)
| Tabela | Modelo | Eventos esperados |
|---|---|---|
| `runtime.outbox_events` | `RuntimeOutboxEventModel` | Eventos de sessão |
| `runtime.inbox_events` | `RuntimeInboxEventModel` | Eventos recebidos |

### Schema `agent` (canônico)
| Tabela | Modelo | Status |
|---|---|---|
| `agent.agent_outbox_events` | `AgentOutboxEventModel` | Ativo, deve permanecer |
| `agent.agent_inbox_events` | `AgentInboxEventModel` | Ativo, deve permanecer |

## Notas

- As tabelas legadas `outbox_events`/`inbox_events` em `ai`, `knowledge` e `runtime` têm o mesmo nome entre si, o que impede `ALTER TABLE ... SET SCHEMA` direto. Será necessário renomear antes ou durante a migração.
- A consolidação deve migrar eventos pendentes e depois descartar ou redirecionar as tabelas legadas.
- `AgentOutboxEventModel` e `AgentInboxEventModel` já estão no schema `agent` e não precisam de migração física.

## Pendências

- Quantidade de eventos pendentes/retryable: não disponível (sem PostgreSQL).
- Eventos que ainda podem ser produzidos para tabelas legadas: requer análise de código runtime.
