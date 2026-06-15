# Diagnosis Seed

Este arquivo não substitui a spec 001. Ele registra os pontos que devem ser confirmados no checkout local:

1. `AIMessage(..., tool_calls=None)` em sync e stream.
2. `except Exception: return []` nos dois loaders.
3. save do turno user antes de load do histórico.
4. append do mesmo `user_message` em `_build_messages`.
5. catch amplo em `_resolve_session` seguido de criação.
6. `list_by_session` com `created_at ASC LIMIT 100`.
7. frontend reutilizando `session_id` recebido via SSE.
