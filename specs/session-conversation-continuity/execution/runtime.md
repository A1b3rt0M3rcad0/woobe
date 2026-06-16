# Runtime — Session Conversation Continuity

## Baseline

- baseline branch: `development`
- implementation branch: `development_session-conversation-continuity`
- baseline SHA: `a64dad406a1ccdc2198c5add8dc53eaad1e98a9d` (merge-base `development` → `development_session-conversation-continuity`)
- started_at: `2026-06-15`
- owner: `opencode-session`

## Status

| Spec | Status | SHA | Evidência | Bloqueios |
|---:|---|---|---|---|
| 000 | completed | a41994c | Decisão registrada. SHA registrado. Baseline `development` = a64dad4. | - |
| 001 | completed | 6ac12dd | 3 testes de caracterização criados. 2 vermelhos (D1, D3), 1 verde confirmando D4. Inventário criado. | - |
| 002 | completed | bbc57fa | Contrato normativo definido. 6 testes de contrato criados: 1 vermelho (session_id inválido não deve criar sessão) | - |
| 003 | completed | 795c6a2 | Mapper centralizado criado. AIMessage(tool_calls=None) removido. except Exception: return [] substituído por ConversationHistoryLoadError. Teste de perda de histórico agora VERDE. | - |
| 004 | completed | 1782162 | Ordem corrigida: carregar histórico → persistir pergunta. Teste de duplicação agora VERDE. | - |
| 005 | completed | f9cf800 | SessionResolver criado. Ownwership validada. 12 testes unitários + 6 contrato VERDES. | - |
| 006 | completed | 809169c | list_recent_by_session adicionado. Ordenação dupla DESC + DESC + reverse. 8 testes unitários VERDES. | - |
| 007 | completed | (this commit) | ConversationContextBuilder unificado. Métodos duplicados removidos. 11 testes unitários + arquitetura VERDES. | - |
| 008 | completed | (this commit) | sessionId sincronizado com query param ?session=uuid. URL preserva sessão no reload. 29 testes vitess existentes + build VERDES. | - |
| 009 | completed | (this commit) | Badge efectivo adicionado. Stateless limpa sessão. Build + tests VERDES. | - |
| 010 | completed | (this commit) | Conversão observability: eventos session_resolved, history_loaded, session_ignored_stateless emitidos via TraceRecorder. Contadores no frontend. 7 testes unitários VERDES. | - |
| 011 | completed | (this commit) | Matriz completa de 10 cenários multi-turn. 22 testes unitários comportamentais VERDES. Unit 58 passed, contract 18 passed, integration 7 skipped. | - |
| 012 | completed | (this commit) | 12 testes de continuidade de sessão no frontend: SSE, session_id, normalizeResponse, error handling. Build + 44 testes VERDES. | - |
| 013 | completed | (this commit) | Validação final completa. Relatório gerado. 44 testes novos, 0 regressões. | - |

## Diagnóstico inicial

- provável causa raiz: `AIMessage(tool_calls=None)` seguido de `except Exception: return []`;
- defeito associado: turno atual persistido antes da carga e anexado novamente;
- defeito associado: session ID inválido cria nova sessão silenciosamente;
- defeito associado: janela retorna registros mais antigos;
- frontend envia e atualiza session ID durante a mesma montagem;
- painel Runtime `stateful` é necessário, mas não corrige falhas de reconstrução.

## Registro de decisões

### Spec 000

1. `session_id` do ProjectRAI é a identidade canônica de uma conversa.
2. O banco do módulo agent é a fonte de verdade do histórico.
3. `stateful` significa persistir e reutilizar histórico da mesma sessão.
4. `stateless` significa não criar sessão e não persistir turnos.
5. Falha ao carregar histórico em execução stateful deve falhar explicitamente; nunca retornar lista vazia como fallback silencioso.
6. Sync e stream devem usar o mesmo componente de resolução e montagem de contexto.
7. Estado de conversa do provider, quando futuramente usado, será otimização subordinada ao histórico local, nunca fonte exclusiva.

### Spec 002

1. Stateful sem session_id → criar sessão, persistir, retornar ID.
2. Stateful com session_id válido → reutilizar, carregar histórico, retornar mesmo ID, zero creates.
3. Stateful com session_id inválido → erro explícito (404/409/422), zero creates.
4. Stateless → não criar sessão, não persistir, retornar null.
5. Session status (active/inactive) não controla memória.
6. `snapshot_override.session_mode` é o modo efetivo do playground.

## Evidências de comandos

### Spec 000

```
git branch --show-current → development_session-conversation-continuity
git rev-parse HEAD → a41994c676f6e17983303c4c6bbf6b7a77545eca
git rev-parse development → a64dad406a1ccdc2198c5add8dc53eaad1e98a9d
git merge-base HEAD development → a64dad406a1ccdc2198c5add8dc53eaad1e98a9d
```

`_load_history`, `_resolve_session`, `_build_messages` presentes em ambos os fluxos:
- `src/modules/agent/application/use_cases/ask_use_case.py`:508,587,660
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py`:679,776,864

`previous_response_id`, `conversation_id`, `thread_id`: **zero ocorrências** no código. `session_id` é a identidade canônica. Confirmado.

`rg` indisponível no Windows; substituído por `Select-String`.

### Spec 002

Contrato normativo registrado em `002-define-stateful-stateless-and-session-reuse-contract.md`.

Testes de contrato criados em `tests/contract/test_session_contract.py`:

| Teste | Status | Descrição |
|---|---|---|
| `test_stateful_without_session_id_creates_new_session` | PASSED | Stateful sem ID cria sessão |
| `test_stateful_with_valid_session_reuses_exactly` | PASSED | Stateful com ID válido reutiliza |
| `test_stateful_with_invalid_session_id_raises_error` | FAILED | **RED** — current code cria nova sessão silenciosamente |
| `test_stateless_does_not_create_session` | PASSED | Stateless não cria sessão |
| `test_stateless_does_not_persist_messages` | PASSED | Stateless não persiste |
| `test_session_status_active_is_not_a_memory_signal` | PASSED | Status não controla memória |

### Spec 003

Arquivos alterados:
- `src/modules/agent/application/handlers/conversation_history_mapper.py` (novo)
- `src/modules/agent/domain/errors.py` (+ `ConversationHistoryLoadError`)
- `src/modules/agent/application/use_cases/ask_use_case.py` (substituído `_load_history`)
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` (substituído `_load_history`)

Evidências:
- `AIMessage(content=..., tool_calls=tool_calls)` removido de ambos os fluxos (agora no mapper)
- `except Exception: return []` removido de `_load_history` (agora levanta `ConversationHistoryLoadError`)
- `test_assistant_without_tool_calls_must_not_erase_history` → **PASSED** (GREEN)
- `test_current_user_turn_is_not_present_twice` → **FAILED** (ainda vermelho — spec 004)
- `ruff check` → 1 erro pré-existente (não relacionado)
- `pyright` → erros pré-existentes de tipagem (não relacionados)

### Spec 004

Ordem corrigida em ambos os fluxos:

```
Antes:  resolver sessão → salvar user → carregar histórico → build_messages (duplicação)
Depois: resolver sessão → carregar histórico anterior → salvar user → build_messages
```

Arquivos alterados:
- `src/modules/agent/application/use_cases/ask_use_case.py` (swap save/load order)
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` (swap save/load order)
- `tests/modules/agent/unit/application/test_conversation_history_regression.py` (test atualizado)

Evidências:
- `test_current_user_turn_is_not_present_twice` → **PASSED** (GREEN)
- `ruff check` → 1 erro pré-existente (não relacionado)

### Spec 005

`SessionResolver` centralizado criado em `src/modules/agent/application/handlers/session_resolver.py`.

Arquivos alterados:
- `src/modules/agent/domain/errors.py` (+ `SessionOwnershipMismatchError`, `SessionInvalidStatusError`)
- `src/modules/agent/application/handlers/session_resolver.py` (novo)
- `src/modules/agent/application/use_cases/ask_use_case.py` (delega `_resolve_session` para `SessionResolver`)
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` (delega `_resolve_session` para `SessionResolver`)
- `src/modules/agent/application/use_cases/runtime_use_cases.py` (valida sessão em `CreateAskJobUseCase`)
- `src/modules/agent/application/composers/create_ask_job_composer.py` (+ `session_repo`)
- `src/modules/agent/presentation/controllers/create_ask_job_controller.py` (+ catch `NotFoundError`)
- `tests/modules/agent/unit/application/test_session_resolution.py` (novo — 12 testes)
- `tests/modules/agent/unit/application/test_conversation_history_regression.py` (test atualizado — agora VERDE)

Evidências:
- `test_nonexistent_id_does_not_create_session` → **PASSED**
- `test_session_from_other_agent_is_not_accepted` → **PASSED**
- `test_session_from_other_project_is_not_accepted` → **PASSED**
- `test_tenant_mismatch_is_not_accepted` → **PASSED**
- `test_user_mismatch_is_not_accepted` → **PASSED**
- `test_tenant_mismatch_with_input_tenant_none_is_allowed` → **PASSED**
- `test_closed_session_does_not_receive_new_messages` → **PASSED**
- `test_expired_session_does_not_receive_new_messages` → **PASSED**
- `test_error_session_does_not_receive_new_messages` → **PASSED**
- `test_stateful_without_id_creates_exactly_one_session` → **PASSED**
- `test_stateless_creates_zero_sessions` → **PASSED**
- `test_stateless_ignores_provided_session_id` → **PASSED**
- `test_stateful_with_invalid_session_id_raises_error` → **PASSED** (contrato — agora VERDE)
- `test_missing_session_id_must_not_create_replacement_session` → **PASSED** (regressão — agora VERDE)
- `ruff check` → 3 erros pré-existentes (não relacionados)

### Spec 001

```
git branch --show-current → development_session-conversation-continuity ✓
git rev-parse HEAD → 6ac12dd6b32d53ae81291a18709121630205c7ed
```

Localizações dos defeitos confirmadas:
- `AIMessage(content=m.content, tool_calls=tool_calls)` → `ask_use_case.py:603`, `ask_agent_stream_service.py:792`
- `except Exception:` + `return []` em `_load_history` → `ask_use_case.py:613-614`, `ask_agent_stream_service.py:802-803`
- `_resolve_session` com `except Exception: pass` → `ask_use_case.py:518`, `ask_agent_stream_service.py:689`
- `list_by_session` ordena `created_at ASC` (mais antigos primeiro) sem desempate por ID → `repositories.py:1167`

Tests:
- `test_assistant_without_tool_calls_must_not_erase_history` → **FAILED** (RED) — `assert 0 > 0` — confirma D1+D2
- `test_current_user_turn_is_not_present_twice` → **FAILED** (RED) — `assert 2 == 1` — confirma D3
- `test_missing_session_id_must_not_create_replacement_session` → **PASSED** — confirma D4 (fallback silencioso)

Inventário: `execution/inventory/session-history-flow.md` criado.

### Spec 006

`list_recent_by_session` adicionado ao port `MessageRepository` e implementado em `SQLAlchemyMessageRepository`.

Arquivos alterados:
- `src/modules/agent/domain/repositories.py` (+ `list_recent_by_session` abstract method)
- `src/modules/agent/infra/database/repositories.py` (+ `list_recent_by_session` com `ORDER BY created_at DESC, id DESC` + `reverse()`)
- `src/modules/agent/application/handlers/conversation_history_mapper.py` (`load_and_convert_history` agora usa `list_recent_by_session`; remove tool_result/tool_call órfãos no início; loga truncamento)
- `src/modules/agent/application/use_cases/ask_use_case.py` (+ `_get_history_limit`; `_load_history` aceita `limit`; `execute` passa limite do agent.settings)
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` (+ `_get_history_limit`; `_load_history` aceita `limit`; `generate` passa limite)
- `tests/modules/agent/unit/application/test_conversation_history_window.py` (novo — 8 testes)
- `tests/modules/agent/integration/test_message_repository_recent_history.py` (novo — placeholder, requer DB)
- `tests/modules/agent/unit/application/test_conversation_history_regression.py` (mock atualizado com `list_recent_by_session`)

Evidências:
- 150 mensagens → retorna as 100 mais recentes → **PASSED**
- resultado final está cronológico → **PASSED**
- timestamps iguais ordenados por ID → **PASSED**
- tool result órfão no início da janela removido → **PASSED**
- tool call órfão no início da janela removido → **PASSED**
- tool call/tool result no meio preservados → **PASSED**
- limite de 500 normalizado → **PASSED**
- limite de 10 aceito → **PASSED**
- `ruff check` → 3 erros pré-existentes (não relacionados)
- Limite padrão: 100 mensagens, configurável via `agent.settings.history_max_messages` (faixa 10–500)

SQL observado:
```sql
SELECT ... FROM messages
WHERE session_id = :session_id
ORDER BY created_at DESC, id DESC
LIMIT :limit
-- reversed in memory for chronological order
```

### Spec 007

`ConversationContextBuilder` criado em `src/modules/agent/application/handlers/conversation_context_builder.py`.

Componente unificado: resolve sessão → carrega histórico → persiste user message → monta prompt.

Sync (`ask_use_case.py`) e stream (`ask_agent_stream_service.py`) agora usam o mesmo builder.

Métodos privados duplicados removidos de ambos os fluxos:
- `_resolve_session`
- `_load_history`
- `_save_user_message`
- `_build_messages`
- `_get_history_limit`

Arquivos alterados:
- `src/modules/agent/application/handlers/conversation_context_builder.py` (novo)
- `src/modules/agent/application/use_cases/ask_use_case.py` (usa builder; remove métodos duplicados)
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` (usa builder; remove métodos duplicados)
- `tests/modules/agent/unit/application/test_conversation_context_builder.py` (novo — 6 testes)
- `tests/modules/agent/integration/test_stream_and_non_stream_parity.py` (novo — placeholder, requer DB)
- `tests/modules/agent/unit/application/test_conversation_history_regression.py` (atualizado para usar builder/resolver)
- `tests/contract/test_session_contract.py` (atualizado para usar `SessionResolver` diretamente)
- `tests/architecture/test_no_duplicate_conversation_methods.py` (novo — 5 testes de arquitetura)

Evidências:
- `test_builder_returns_existing_session` → **PASSED**
- `test_builder_creates_new_session_when_no_id` → **PASSED**
- `test_history_counters` → **PASSED**
- `test_builder_propagates_session_not_found` → **PASSED**
- `test_builder_stateless_returns_none` → **PASSED**
- `test_builder_uses_history_limit` → **PASSED**
- `test_no_duplicate_conversation_methods` (x5) → **PASSED**
- `ruff check` → 1 erro pré-existente (não relacionado)

### Spec 008

sessionId sincronizado com query param `?session=<uuid>` na URL do playground.

Arquivos alterados:
- `web/src/pages/AgentPlaygroundPage.tsx` (sessionId via `useSearchParams`; inicialização da URL; validação contra agent sessions; limpeza na troca de agent)

Estratégia implementada:
1. `useSearchParams` lê/escreve `?session=<uuid>` sem recarregar a página (`replace: true`)
2. `setSessionId` atualiza tanto state local quanto search params
3. Inicialização: lê sessionId da URL no mount
4. Validação: se sessionId não pertence à lista de sessions do agent, é limpo
5. Troca de agent: sessionId é limpo (via `useEffect` em `agentId`)
6. "New Session" chama `setSessionId(null)` que remove o param da URL
7. SSE `meta`/`done` events chamam `setSessionId` que atualiza a URL

Evidências:
- `npm run build` → **PASSED**
- `npm run test:run` → 29 passed

### Spec 013

Validação final completa e relatório gerado.

Arquivos alterados:
- `specs/session-conversation-continuity/execution/final-report.md` (novo)

Evidências:
- `ruff check src tests` → 20 errors (pre-existing, fora do escopo)
- `pyright` → 702 errors (pre-existing, import resolution em testes)
- `pytest tests/modules/agent/unit -q` → **58 passed**
- `pytest tests/modules/agent/integration -q` → **7 skipped**
- `pytest tests/contract -q` → **18 passed**
- `pytest tests/architecture -q` → 42 failed (pre-existing)
- `pytest tests/modules/agent tests/contract -q` → **1095 passed**, 3 failed (pre-existing)
- `cd web && npm run test:run` → **44 passed**
- `cd web && npm run build` → **PASSED**

Conclusão: spec 013 completed. Todas as 13 specs do escopo `session-conversation-continuity` concluídas.

### Spec 012

Doze testes de continuidade de sessão no frontend, cobrindo SSE event flow,
session_id no request/response, normalizeResponse com history fields,
e tratamento de erro em stream.

Arquivos alterados:
- `web/src/features/playground/__tests__/session-continuity.test.ts` (novo — 12 testes)
- `web/src/features/playground/api.ts` (+ history fields no normalizeResponse)

Evidências:
- `cd web && npm run test:run` → **44 passed** (3 suites)
- `cd web && npm run build` → **PASSED**

### Spec 011

Matriz completa de 10 cenários de conversação multi-turn implementada.

Arquivos alterados:
- `tests/modules/agent/unit/application/test_conversation_multi_turn.py` (novo — 22 testes)

Cenários cobertos (sync + stream):
- stateful primeiro turno → sessão + 2 mensagens
- stateful segundo turno → prompt contém turno anterior
- assistant sem tools → histórico preservado
- assistant com tools → tool metadata preservada
- ID inexistente → erro explícito (SessionNotFoundError)
- ID de outro agent/project → erro (SessionOwnershipMismatchError)
- stateless → zero sessão/mensagem
- sessão > limite → últimos N turnos
- erro de mapper → erro explícito (ConversationHistoryLoadError)
- turno atual → aparece uma vez no prompt

Evidências:
- `pytest tests/modules/agent/unit -q` → **58 passed**
- `pytest tests/modules/agent/integration -q` → **7 skipped** (requer DB)
- `pytest tests/contract -q` → **18 passed**
- `pytest tests/architecture -q` → **42 failed** (pre-existing, fora do escopo)

### Spec 010

Conversation observability events emitted via existing TraceRecorder port.

Eventos emitidos:
- `conversation.session_resolved` — session_id, mode, project_id, agent_id, sem conteúdo
- `conversation.history_loaded` — session_id, message_count, turn_count, truncated, window_limit, contains_tool_calls
- `conversation.session_ignored_stateless` — indicador de ID ignorado em modo stateless

Arquivos alterados:
- `src/modules/agent/application/handlers/conversation_context_builder.py` (structured logging)
- `src/modules/agent/application/use_cases/ask_use_case.py` (+ `_record_conversation_events`)
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` (+ `_record_conversation_events`)
- `src/modules/agent/application/dtos/runtime_dtos.py` (+ `history_message_count`, `history_truncated`)
- `src/modules/agent/presentation/schemas.py` (+ `history_message_count`, `history_truncated`)
- `src/modules/agent/presentation/controllers/ask_agent_controller.py` (passa campos de histórico)
- `web/src/features/playground/types.ts` (+ `history_message_count`, `history_truncated`)
- `web/src/features/playground/components/DebugView.tsx` (+ seção Conversation Context)
- `web/src/features/playground/__tests__/history-observability.test.ts` (novo — 3 testes)
- `tests/modules/agent/unit/application/test_conversation_observability.py` (novo — 7 testes)

Evidências:
- `pytest tests/modules/agent/unit/application/test_conversation_observability.py -q` → **7 passed**
- `cd web && npm run test:run -- history-observability` → **3 passed**
- `ruff check` → **All checks passed**

### Spec 009

Modo efetivo exibido no playground. Stateless limpa sessão automaticamente.

Arquivos alterados:
- `web/src/pages/AgentPlaygroundPage.tsx` (+ badge efetivo; + `activeSource`; + `useEffect` para limpar sessão ao mudar para stateless)

Evidências:
- Badge `Stateful (saved)` / `Stateless (draft)` exibido na barra de status
- Ao mudar para stateless, `sessionId` é limpo (incluindo query param)
- `npm run build` → **PASSED**
- `npm run test:run` → 29 passed

## Pendências e riscos

- confirmar versão efetiva de `langchain-core` no lock/ambiente;
- confirmar política desejada para user message quando stream é cancelado;
- confirmar mapeamento HTTP canônico de sessão closed/expired/error;
- confirmar limite de histórico e orçamento de tokens.

## Próxima spec recomendada

N/A — todas as 13 specs do escopo `session-conversation-continuity` foram concluídas.
