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
| 001 | pending | - | - | - |
| 002 | pending | - | - | - |
| 003 | pending | - | - | - |
| 004 | pending | - | - | - |
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

## Pendências e riscos

- confirmar versão efetiva de `langchain-core` no lock/ambiente;
- confirmar política desejada para user message quando stream é cancelado;
- confirmar mapeamento HTTP canônico de sessão closed/expired/error;
- confirmar limite de histórico e orçamento de tokens.

## Próxima spec recomendada

**001** — reproduce-and-inventory-session-history-failure
