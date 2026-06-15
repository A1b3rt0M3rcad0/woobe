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
| 005 | pending | - | - | - |
| 006 | pending | - | - | - |
| 007 | pending | - | - | - |
| 008 | pending | - | - | - |
| 009 | pending | - | - | - |
| 010 | pending | - | - | - |
| 011 | pending | - | - | - |
| 012 | pending | - | - | - |
| 013 | pending | - | - | - |

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

## Pendências e riscos

- confirmar versão efetiva de `langchain-core` no lock/ambiente;
- confirmar política desejada para user message quando stream é cancelado;
- confirmar mapeamento HTTP canônico de sessão closed/expired/error;
- confirmar limite de histórico e orçamento de tokens.

## Próxima spec recomendada

**005** — harden-session-resolution-and-ownership
