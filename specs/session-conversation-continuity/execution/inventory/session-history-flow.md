# Inventário do Fluxo de Sessão/Histórico

## 1. Consumidores do fluxo

| Consumidor | Arquivo | Síncrono/Stream/Job | Session | Histórico |
|---|---|---|---|---|
| AskAgentUseCase.execute | `src/modules/agent/application/use_cases/ask_use_case.py` | sync | `_resolve_session` | `_load_history` + `_build_messages` |
| AskAgentStreamService.generate | `src/modules/agent/application/use_cases/ask_agent_stream_service.py` | stream | `_resolve_session` | `_load_history` + `_build_messages` |
| (futuro) AskJob | `src/modules/agent/domain/entities.py` (AskJob) | job | via use case | via use case |

## 2. Endpoints HTTP

| Rota | Controller | Método |
|---|---|---|
| `/runtime/ask` | (POST) — controller não identificado neste inventário | sync |
| `/runtime/ask/stream` | (GET/SSE) — controller não identificado neste inventário | stream |

## 3. Repositórios

| Repositório | Métodos de sessão | Métodos de mensagem |
|---|---|---|
| `SQLAlchemySessionRepository` | `create`, `get_by_id`, `update` | — |
| `SQLAlchemyMessageRepository` | — | `create`, `list_by_session`, `paginate_by_session`, `count_by_session` |

## 4. Defeitos confirmados

| ID | Defeito | Localização | Linha |
|---|---|---|---|
| D1 | `AIMessage(content=..., tool_calls=None)` falha validação Pydantic | `ask_use_case.py` | 603 |
| D1 | (duplicado) | `ask_agent_stream_service.py` | 792 |
| D2 | `except Exception: return []` suprime erro do histórico | `ask_use_case.py` | 613-614 |
| D2 | (duplicado) | `ask_agent_stream_service.py` | 802-803 |
| D3 | `_save_user_message` antes de `_load_history` + `_build_messages` anexa turno atual duas vezes | `ask_use_case.py` | 140-148 |
| D3 | (duplicado) | `ask_agent_stream_service.py` | 126-153 |
| D4 | `_resolve_session` captura `Exception` genérico e cria nova sessão | `ask_use_case.py` | 517-519 |
| D4 | (duplicado) | `ask_agent_stream_service.py` | 688-690 |
| D5 | `list_by_session` ordena `created_at ASC` sem desempate por ID | `repositories.py` | 1161-1172 |

## 5. Frontend

| Arquivo | Relevância |
|---|---|
| `web/src/pages/AgentPlaygroundPage.tsx` | Envia `session_id`, captura dos eventos `meta`/`done` |
| `web/src/features/playground/api.ts` | Serializa `session_id` no request |
| `web/src/features/playground/components/AgentSettingsTab.tsx` | Painel Runtime: `stateful`/`stateless` e `active`/`inactive` |
| `web/src/features/playground/AgentEditorContext.tsx` | `snapshot_override` inclui `session_mode` |
